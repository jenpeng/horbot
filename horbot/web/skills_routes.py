"""Skills API routes."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel


ResolveSkillDirFn = Callable[[Optional[str]], tuple[Any | None, Path, Path]]
DescribeSkillSourceFn = Callable[..., dict[str, Any]]


class SkillCreateRequest(BaseModel):
    name: str
    content: str


class SkillUpdateRequest(BaseModel):
    content: str


def create_skills_router(
    resolve_skill_dir_for_request: ResolveSkillDirFn,
    describe_skill_source: DescribeSkillSourceFn,
) -> APIRouter:
    """Create routes for skill listing and management."""

    router = APIRouter()

    @router.get("/skills")
    async def get_skills(agent_id: Optional[str] = None):
        """Get all skills."""
        from horbot.agent.skill_package import build_skill_compatibility
        from horbot.agent.skills import SkillsLoader

        _, workspace_path, skills_dir = resolve_skill_dir_for_request(agent_id)
        loader = SkillsLoader(workspace=workspace_path, agent_id=agent_id, skills_dir=skills_dir)
        skills = loader.list_skills(filter_unavailable=False, include_disabled=True)

        result = []
        for skill in skills:
            metadata = loader.get_skill_metadata(skill["name"]) or {}
            meta = loader._get_skill_meta(skill["name"])

            compat = meta.get("_compat", {}) if isinstance(meta, dict) else {}
            compatibility = build_skill_compatibility(
                meta=meta if isinstance(meta, dict) else {},
                normalized_from_legacy=bool(compat.get("normalized_from_legacy", False)),
            )
            source_meta = describe_skill_source(skill=skill, metadata=metadata)

            result.append({
                "name": skill["name"],
                "source": skill["source"],
                "path": skill["path"],
                "description": metadata.get("description", skill["name"]),
                "available": loader._check_requirements(meta),
                "enabled": skill.get("enabled", True),
                "always": meta.get("always", False) or metadata.get("always", False),
                "requires": meta.get("requires", {}),
                "schema": compat.get("canonical_schema", "horbot"),
                "schema_version": compat.get("canonical_schema_version", 1),
                "source_schema": compat.get("source_schema", "horbot"),
                "source_schema_version": compat.get("source_schema_version", 1),
                "normalized_from_legacy": bool(compat.get("normalized_from_legacy", False)),
                "install": meta.get("install", []) if isinstance(meta.get("install"), list) else [],
                "missing_requirements": loader._get_missing_requirements(meta) if not loader._check_requirements(meta) else None,
                "compatibility": compatibility,
                **source_meta,
            })

        return {"skills": result}

    @router.get("/skills/{skill_name}")
    async def get_skill_detail(skill_name: str, agent_id: Optional[str] = None):
        """Get skill detail."""
        from horbot.agent.skill_package import build_skill_compatibility
        from horbot.agent.skills import SkillsLoader

        _, workspace_path, skills_dir = resolve_skill_dir_for_request(agent_id)
        loader = SkillsLoader(workspace=workspace_path, agent_id=agent_id, skills_dir=skills_dir)

        content = loader.load_skill(skill_name)
        if not content:
            raise HTTPException(status_code=404, detail="Skill not found")

        skill_info = next(
            (item for item in loader.list_skills(filter_unavailable=False, include_disabled=True) if item["name"] == skill_name),
            None,
        )

        metadata = loader.get_skill_metadata(skill_name) or {}
        meta = loader._get_skill_meta(skill_name)

        compat = meta.get("_compat", {}) if isinstance(meta, dict) else {}
        compatibility = build_skill_compatibility(
            meta=meta if isinstance(meta, dict) else {},
            normalized_from_legacy=bool(compat.get("normalized_from_legacy", False)),
        )
        source_meta = describe_skill_source(
            skill=skill_info or {"source": "user", "path": str(skills_dir / skill_name / "SKILL.md")},
            metadata=metadata,
        )

        return {
            "name": skill_name,
            "path": skill_info["path"] if skill_info else str(skills_dir / skill_name / "SKILL.md"),
            "source": skill_info["source"] if skill_info else "user",
            "content": content,
            "metadata": metadata,
            "description": metadata.get("description", skill_name),
            "available": loader._check_requirements(meta),
            "enabled": skill_info["enabled"] if skill_info else loader._get_skill_enabled(skill_name),
            "always": meta.get("always", False) or metadata.get("always", False),
            "requires": meta.get("requires", {}),
            "schema": compat.get("canonical_schema", "horbot"),
            "schema_version": compat.get("canonical_schema_version", 1),
            "source_schema": compat.get("source_schema", "horbot"),
            "source_schema_version": compat.get("source_schema_version", 1),
            "normalized_from_legacy": bool(compat.get("normalized_from_legacy", False)),
            "install": meta.get("install", []) if isinstance(meta.get("install"), list) else [],
            "missing_requirements": loader._get_missing_requirements(meta) if not loader._check_requirements(meta) else None,
            "compatibility": compatibility,
            **source_meta,
        }

    @router.post("/skills")
    async def create_skill(request: SkillCreateRequest, agent_id: Optional[str] = None):
        """Create a new skill."""
        from horbot.agent.skill_package import validate_skill_content
        from horbot.agent.skills import SkillsLoader

        _, workspace_path, skills_dir = resolve_skill_dir_for_request(agent_id)
        SkillsLoader(workspace=workspace_path, agent_id=agent_id, skills_dir=skills_dir)

        skill_dir = skills_dir / request.name
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            raise HTTPException(status_code=409, detail=f"Skill '{request.name}' already exists")

        validation = validate_skill_content(request.content, expected_name=request.name.strip())
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail="Skill validation failed: " + " ".join(validation["issues"]))

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(request.content, encoding="utf-8")

        return {
            "name": request.name,
            "path": str(skill_file),
            "source": "user",
            "message": f"Skill '{request.name}' created successfully",
        }

    @router.put("/skills/{skill_name}")
    async def update_skill(skill_name: str, request: SkillUpdateRequest, agent_id: Optional[str] = None):
        """Update an existing skill."""
        from horbot.agent.skill_package import validate_skill_content
        from horbot.agent.skills import SkillsLoader

        _, workspace_path, skills_dir = resolve_skill_dir_for_request(agent_id)
        loader = SkillsLoader(workspace=workspace_path, agent_id=agent_id, skills_dir=skills_dir)
        skills = loader.list_skills(filter_unavailable=False)
        skill_info = next((s for s in skills if s["name"] == skill_name), None)

        if not skill_info:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
        if skill_info["source"] == "builtin":
            raise HTTPException(status_code=403, detail="Cannot modify builtin skills")

        skill_path = Path(skill_info["path"])
        validation = validate_skill_content(request.content, expected_name=skill_name)
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail="Skill validation failed: " + " ".join(validation["issues"]))

        skill_path.write_text(request.content, encoding="utf-8")
        return {
            "name": skill_name,
            "path": str(skill_path),
            "message": f"Skill '{skill_name}' updated successfully",
        }

    @router.post("/skills/import")
    async def import_skill_package(
        file: UploadFile = File(...),
        replace_existing: bool = Form(False),
        agent_id: Optional[str] = None,
    ):
        """Import a skill package from .skill or .zip."""
        from horbot.agent.skill_package import build_skill_compatibility, import_skill_archive_bytes

        _, _workspace_path, skills_dir = resolve_skill_dir_for_request(agent_id)
        skills_dir.mkdir(parents=True, exist_ok=True)

        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Uploaded skill package is empty.")
        if len(payload) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Skill package exceeds the 20MB size limit.")

        result = import_skill_archive_bytes(
            payload,
            file.filename or "uploaded.skill",
            skills_dir=skills_dir,
            replace_existing=replace_existing,
        )
        if not result["valid"]:
            raise HTTPException(status_code=400, detail="Skill import failed: " + " ".join(result["issues"]))

        compat = result["meta"].get("_compat", {}) if isinstance(result.get("meta"), dict) else {}
        compatibility = build_skill_compatibility(
            meta=result.get("meta") if isinstance(result.get("meta"), dict) else {},
            normalized_from_legacy=bool(compat.get("normalized_from_legacy", False)),
        )

        return {
            "name": result["skill_name"],
            "path": result["path"],
            "message": f"Skill '{result['skill_name']}' imported successfully",
            "files": result.get("files", []),
            "description": result.get("description", ""),
            "warnings": result.get("warnings", []),
            "compatibility": compatibility,
        }

    @router.post("/skills/consolidate-generated")
    async def consolidate_generated_skills(agent_id: Optional[str] = None):
        """Manually consolidate auto-generated skill families."""
        from horbot.agent.skill_evolution import SkillEvolutionEngine

        _, workspace_path, skills_dir = resolve_skill_dir_for_request(agent_id)
        engine = SkillEvolutionEngine(workspace=workspace_path, agent_id=agent_id, skills_dir=skills_dir)
        result = engine.consolidate_generated_skills()
        return {
            **result,
            "message": (
                f"Consolidated {result['merged_skill_count']} generated skills "
                f"across {len(result['updated_families'])} skill families."
            ),
        }

    @router.post("/skills/{skill_name}/promote")
    async def promote_skill_to_builtin(skill_name: str, agent_id: Optional[str] = None):
        """Promote a user skill into the project builtin skills directory."""
        from horbot.agent.skills import BUILTIN_SKILLS_DIR, SkillsLoader

        _, workspace_path, skills_dir = resolve_skill_dir_for_request(agent_id)
        loader = SkillsLoader(workspace=workspace_path, agent_id=agent_id, skills_dir=skills_dir)
        skills = loader.list_skills(filter_unavailable=False, include_disabled=True)
        skill_info = next((s for s in skills if s["name"] == skill_name), None)

        if not skill_info:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
        if skill_info["source"] == "builtin":
            raise HTTPException(status_code=403, detail="Skill is already a builtin skill")

        source_path = Path(skill_info["path"])
        target_dir = BUILTIN_SKILLS_DIR / skill_name
        target_file = target_dir / "SKILL.md"
        if target_dir.exists() or target_file.exists():
            raise HTTPException(status_code=409, detail=f"Builtin skill '{skill_name}' already exists")

        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if source_path.name == "SKILL.md":
            shutil.copytree(source_path.parent, target_dir)
            shutil.rmtree(source_path.parent)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
            source_path.unlink()

        return {
            "name": skill_name,
            "path": str(target_file),
            "source": "builtin",
            "message": f"Skill '{skill_name}' promoted to builtin successfully",
        }

    @router.delete("/skills/{skill_name}")
    async def delete_skill(skill_name: str, agent_id: Optional[str] = None):
        """Delete a skill."""
        from horbot.agent.skills import SkillsLoader

        _, workspace_path, skills_dir = resolve_skill_dir_for_request(agent_id)
        loader = SkillsLoader(workspace=workspace_path, agent_id=agent_id, skills_dir=skills_dir)
        skills = loader.list_skills(filter_unavailable=False)
        skill_info = next((s for s in skills if s["name"] == skill_name), None)

        if not skill_info:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
        if skill_info["source"] == "builtin":
            raise HTTPException(status_code=403, detail="Cannot delete builtin skills")

        skill_path = Path(skill_info["path"])
        if skill_path.name == "SKILL.md":
            shutil.rmtree(skill_path.parent)
        else:
            skill_path.unlink()

        return {
            "name": skill_name,
            "message": f"Skill '{skill_name}' deleted successfully",
        }

    @router.patch("/skills/{skill_name}/toggle")
    async def toggle_skill(skill_name: str, agent_id: Optional[str] = None):
        """Toggle skill enabled status."""
        from horbot.agent.skills import SkillsLoader

        _, workspace_path, skills_dir = resolve_skill_dir_for_request(agent_id)
        loader = SkillsLoader(workspace=workspace_path, agent_id=agent_id, skills_dir=skills_dir)

        content = loader.load_skill(skill_name)
        if not content:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        current_enabled = loader._get_skill_enabled(skill_name)
        new_enabled = not current_enabled

        if content.startswith("---"):
            match = re.match(r"^(---\n)(.*?)(\n---\n)(.*)", content, re.DOTALL)
            if not match:
                raise HTTPException(status_code=500, detail="Failed to parse skill frontmatter")
            frontmatter = match.group(2)
            body = match.group(4)
            if "enabled:" in frontmatter:
                frontmatter = re.sub(r"enabled:\s*\S+", f"enabled: {str(new_enabled).lower()}", frontmatter)
            else:
                frontmatter += f"\nenabled: {str(new_enabled).lower()}"
            new_content = f"---\n{frontmatter}\n---\n{body}"
        else:
            new_content = f"---\nname: {skill_name}\nenabled: {str(new_enabled).lower()}\n---\n\n{content}"

        skills = loader.list_skills(filter_unavailable=False, include_disabled=True)
        skill_info = next((s for s in skills if s["name"] == skill_name), None)
        if skill_info:
            Path(skill_info["path"]).write_text(new_content)

        return {
            "name": skill_name,
            "enabled": new_enabled,
            "message": f"Skill '{skill_name}' {'enabled' if new_enabled else 'disabled'} successfully",
        }

    return router
