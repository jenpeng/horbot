"""Upload, preview, and live artifact API routes."""

from pathlib import Path
from typing import Any, Dict, List
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from loguru import logger
from pydantic import BaseModel, Field

from horbot.web import upload_preview as upload_preview_module
from horbot.web.artifacts import (
    ArtifactValidationError,
    cleanup_expired_artifacts,
    render_artifact,
    resolve_runtime_artifact_file,
)
from horbot.web.upload_preview import (
    MAX_FILE_SIZE,
    UploadResponse,
    _build_preview_url,
    _cleanup_pptx_pdf_preview,
    _clear_remote_image_cache,
    _dedupe_display_filename,
    _extract_document_content,
    _get_file_category,
    _get_remote_image_cache_stats,
    _pptx_slide_count,
    _pptx_slide_image_paths,
    _render_docx_preview_html,
    _render_pptx_preview_html,
    _render_pptx_slide_image,
    _resolve_display_filename,
    _resolve_upload_mime_type,
    _resolve_uploaded_file_by_id,
    _upload_metadata_path,
    _write_upload_metadata,
)

router = APIRouter()

INLINE_PREVIEW_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
}


class ArtifactRenderRequest(BaseModel):
    spec: Dict[str, Any]
    ttl_seconds: int = Field(default=1800, ge=60, le=86400)


@router.post("/upload", response_model=List[UploadResponse])
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload multiple files."""
    upload_dir = upload_preview_module._get_upload_dir()
    results = []
    seen_display_names: set[str] = set()

    for file in files:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File {file.filename} exceeds maximum size of 50MB",
            )

        file_id = str(uuid.uuid4())
        original_name = _dedupe_display_filename(
            _resolve_display_filename(file.filename, fallback_stem="uploaded-file"),
            seen_display_names,
        )
        mime_type = _resolve_upload_mime_type(
            filename=original_name,
            declared_mime_type=file.content_type,
        )
        category = _get_file_category(mime_type)

        ext = Path(original_name).suffix
        stored_filename = f"{file_id}{ext}"
        file_path = upload_dir / stored_filename

        with open(file_path, "wb") as f:
            f.write(content)

        minimax_file_id = None
        extracted_text = None
        if category == "document":
            extracted_text = _extract_document_content(file_path, mime_type)
            if extracted_text:
                logger.info("Extracted {} characters from {}", len(extracted_text), original_name)

        _write_upload_metadata(
            file_id=file_id,
            stored_filename=stored_filename,
            original_name=original_name,
            mime_type=mime_type,
            size=len(content),
            category=category,
        )

        result = UploadResponse(
            file_id=file_id,
            filename=original_name,
            original_name=original_name,
            stored_filename=stored_filename,
            mime_type=mime_type,
            size=len(content),
            category=category,
            url=f"/api/files/{file_id}",
            preview_url=_build_preview_url(file_id, mime_type, category),
            minimax_file_id=minimax_file_id,
            extracted_text=extracted_text,
        )
        results.append(result)
        logger.info(
            "Uploaded file: {} -> {} (display={}, {})",
            file.filename,
            stored_filename,
            original_name,
            category,
        )

    return results


@router.get("/files/{file_id}")
async def get_file(file_id: str):
    """Get uploaded file by ID."""
    file_path, metadata = _resolve_uploaded_file_by_id(file_id)
    download_name = str((metadata or {}).get("original_name") or file_path.name).strip() or file_path.name
    mime_type = _resolve_upload_mime_type(
        filename=download_name,
        declared_mime_type=str((metadata or {}).get("mime_type") or ""),
    )

    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=download_name,
        content_disposition_type="inline",
    )


@router.get("/files/{file_id}/preview")
async def get_file_preview(file_id: str):
    """Get file preview for files that support embedded rendering."""
    file_path, metadata = _resolve_uploaded_file_by_id(file_id)
    display_name = str((metadata or {}).get("original_name") or file_path.name).strip() or file_path.name
    mime_type = _resolve_upload_mime_type(
        filename=display_name,
        declared_mime_type=str((metadata or {}).get("mime_type") or ""),
    )

    if mime_type.startswith("image/") or mime_type == "application/pdf":
        return FileResponse(
            path=file_path,
            media_type=mime_type,
            filename=display_name,
            content_disposition_type="inline",
            headers=INLINE_PREVIEW_HEADERS,
        )

    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return HTMLResponse(_render_docx_preview_html(file_path, display_name), headers=INLINE_PREVIEW_HEADERS)

    if mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        return HTMLResponse(_render_pptx_preview_html(file_id, file_path, display_name), headers=INLINE_PREVIEW_HEADERS)

    raise HTTPException(status_code=400, detail="Preview only available for supported inline file types")


@router.post("/files/{file_id}/preview/cleanup")
async def cleanup_pptx_preview(file_id: str):
    """Cleanup transient intermediate files for a PPTX preview session."""
    file_path, metadata = _resolve_uploaded_file_by_id(file_id)
    display_name = str((metadata or {}).get("original_name") or file_path.name).strip() or file_path.name
    mime_type = _resolve_upload_mime_type(
        filename=display_name,
        declared_mime_type=str((metadata or {}).get("mime_type") or ""),
    )
    if mime_type != "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        raise HTTPException(status_code=400, detail="Preview cleanup is only available for PowerPoint files")
    return {"ok": True, "removed_pdf": _cleanup_pptx_pdf_preview(file_path)}


@router.get("/files/{file_id}/preview/slides/{page}")
async def get_pptx_preview_slide_image(file_id: str, page: int):
    """Serve a rendered PPTX slide image from the LibreOffice PDF preview."""
    file_path, metadata = _resolve_uploaded_file_by_id(file_id)
    display_name = str((metadata or {}).get("original_name") or file_path.name).strip() or file_path.name
    mime_type = _resolve_upload_mime_type(
        filename=display_name,
        declared_mime_type=str((metadata or {}).get("mime_type") or ""),
    )
    if mime_type != "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        raise HTTPException(status_code=400, detail="Slide image preview is only available for PowerPoint files")

    image_path, _engine = _render_pptx_slide_image(file_path, page)
    if not image_path:
        raise HTTPException(status_code=404, detail="Slide image not found")

    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename=f"{Path(display_name).stem}-slide-{page:03d}.png",
        content_disposition_type="inline",
        headers=INLINE_PREVIEW_HEADERS,
    )


@router.get("/files/{file_id}/preview-capabilities")
async def get_file_preview_capabilities(file_id: str):
    """Describe which document preview renderer will be used for this file."""
    file_path, metadata = _resolve_uploaded_file_by_id(file_id)
    display_name = str((metadata or {}).get("original_name") or file_path.name).strip() or file_path.name
    mime_type = _resolve_upload_mime_type(
        filename=display_name,
        declared_mime_type=str((metadata or {}).get("mime_type") or ""),
    )
    preview_url = _build_preview_url(file_id, mime_type, _get_file_category(mime_type))

    if mime_type.startswith("image/"):
        return {
            "file_id": file_id,
            "filename": display_name,
            "mime_type": mime_type,
            "supported": True,
            "renderer": "image",
            "preview_url": preview_url,
        }
    if mime_type == "application/pdf":
        return {
            "file_id": file_id,
            "filename": display_name,
            "mime_type": mime_type,
            "supported": True,
            "renderer": "pdf",
            "preview_url": preview_url,
        }
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return {
            "file_id": file_id,
            "filename": display_name,
            "mime_type": mime_type,
            "supported": True,
            "renderer": "html-docx",
            "preview_url": preview_url,
        }
    if mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        cached_images = _pptx_slide_image_paths(file_path)
        renderer, visual_pages = upload_preview_module._pptx_visual_preview_plan(file_path)
        libreoffice_command = upload_preview_module._find_soffice_command()
        return {
            "file_id": file_id,
            "filename": display_name,
            "mime_type": mime_type,
            "supported": True,
            "renderer": renderer,
            "preview_url": preview_url,
            "slide_count": _pptx_slide_count(file_path),
            "visual_pages": visual_pages,
            "rendered_pages": len(cached_images),
            "engines": [
                {
                    "id": "libreoffice",
                    "available": bool(libreoffice_command),
                    "command": libreoffice_command,
                }
            ],
        }
    return {
        "file_id": file_id,
        "filename": display_name,
        "mime_type": mime_type,
        "supported": False,
        "renderer": "download",
        "preview_url": None,
    }


@router.post("/artifacts/render")
async def create_live_artifact_render(request: ArtifactRenderRequest):
    """Create an ephemeral sandbox render from a structured renderable spec."""
    try:
        return render_artifact(request.spec, ttl_seconds=request.ttl_seconds)
    except ArtifactValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Live artifact render failed")
        raise HTTPException(status_code=500, detail=f"Live artifact render failed: {exc}") from exc


@router.get("/artifacts/runtime/{artifact_id}/{filename}")
async def serve_live_artifact_runtime_file(artifact_id: str, filename: str):
    """Serve a generated runtime artifact file."""
    try:
        file_path = resolve_runtime_artifact_file(artifact_id, filename)
    except ArtifactValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Rendered artifact has expired or does not exist") from exc
    return FileResponse(
        file_path,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none';",
        },
    )


@router.delete("/artifacts/runtime/expired")
async def delete_expired_live_artifacts():
    """Manually clean expired temporary render files."""
    return {"removed": cleanup_expired_artifacts()}


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Delete uploaded file by ID."""
    file_path, _metadata = _resolve_uploaded_file_by_id(file_id)
    file_path.unlink(missing_ok=True)
    _upload_metadata_path(file_id).unlink(missing_ok=True)
    logger.info("Deleted file: {}", file_path)

    return {"status": "success", "message": f"File {file_id} deleted"}


@router.get("/files/cache/remote-images")
async def get_remote_image_cache_status():
    """Get remote image cache stats."""
    try:
        stats = _get_remote_image_cache_stats()
        return {
            "status": "success",
            **stats,
        }
    except Exception as e:
        logger.error("Failed to get remote image cache stats: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get remote image cache stats: {str(e)}")


@router.delete("/files/cache/remote-images")
async def clear_remote_image_cache():
    """Clear cached remote images imported into uploads."""
    try:
        result = _clear_remote_image_cache()
        return {
            "status": "success",
            **result,
        }
    except Exception as e:
        logger.error("Failed to clear remote image cache: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to clear remote image cache: {str(e)}")
