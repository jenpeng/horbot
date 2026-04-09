"""Web server main application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import time
import sys
from loguru import logger

from horbot.web import api as api_module
from horbot.web.api import router as api_router
from horbot.web.security import authorize_http_request, sanitize_json_text
from horbot.web.websocket import router as websocket_router
from horbot.utils.paths import get_logs_dir

_channel_manager = None


def setup_logging():
    """Configure loguru logging with file output."""
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    logger.remove()
    
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG"
    )
    
    logger.add(
        logs_dir / "backend.log",
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        encoding="utf-8"
    )
    
    logger.add(
        logs_dir / "api_requests.log",
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
        level="INFO",
        encoding="utf-8",
        filter=lambda record: record["extra"].get("type") == "api_request"
    )
    
    logger.info("Logging configured. Backend log: {}", logs_dir / "backend.log")


class RequestLoggingMiddleware:
    """Middleware to log all API requests and responses."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # SSE endpoints are sensitive to middleware buffering/wrapping.
        # Let them pass through untouched so streaming starts immediately.
        if scope.get("path") == "/api/chat/stream":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        
        start_time = time.time()
        
        request_body_bytes = None
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                request_body_bytes = await request.body()
                request_body = request_body_bytes.decode("utf-8", errors="replace")
                if len(request_body) > 500:
                    request_body = request_body[:500] + "..."
                request_body = sanitize_json_text(request_body)
            except Exception:
                request_body = "<unable to read body>"
        
        response_body = bytearray()
        status_code = None
        body_replayed = False
        
        async def receive_wrapper():
            nonlocal body_replayed
            if request_body_bytes is not None:
                if not body_replayed:
                    body_replayed = True
                    return {"type": "http.request", "body": request_body_bytes, "more_body": False}
                return {"type": "http.request", "body": b"", "more_body": False}
            return await receive()
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                response_body.extend(message.get("body", b""))
            await send(message)
        
        await self.app(scope, receive_wrapper, send_wrapper)
        
        process_time = time.time() - start_time
        
        response_body_str = None
        try:
            response_body_str = response_body.decode("utf-8", errors="replace")
            if len(response_body_str) > 500:
                response_body_str = response_body_str[:500] + "..."
            response_body_str = sanitize_json_text(response_body_str)
        except Exception:
            response_body_str = "<unable to read body>"
        
        log_data = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query": str(request.query_params),
            "status_code": status_code,
            "process_time_ms": round(process_time * 1000, 2),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
        }
        
        if request_body:
            log_data["request_body"] = request_body
        if response_body_str and status_code and status_code >= 400:
            log_data["response_body"] = response_body_str
        
        logger.bind(type="api_request").info(
            "API Request: {method} {url} - {status_code} ({process_time_ms}ms) - Client: {client_ip}",
            **log_data
        )


class SecurityMiddleware:
    """Reject remote API access unless explicitly authorized."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        try:
            authorize_http_request(request)
        except FastAPIHTTPException as exc:
            from fastapi.responses import JSONResponse

            response = JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers or None,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    setup_logging()
    logger.info("Starting Horbot Web UI...")
    
    cron_service = api_module.get_cron_service()
    await api_module.setup_cron_callback()
    await cron_service.start()
    
    yield
    
    logger.info("Shutting down Horbot Web UI...")
    cron_service.stop()


# Create FastAPI application
app = FastAPI(
    title="Horbot Web UI",
    description="Web interface for Horbot AI assistant",
    version="0.1.0",
    lifespan=lifespan
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Horbot-Admin-Token", "X-Workhorse-Admin-Token"],
)

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(websocket_router, prefix="/ws")

# Frontend directory
frontend_dir = Path(__file__).parent / "frontend" / "dist"

# Serve static assets
if frontend_dir.exists():
    assets_dir = frontend_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

# Catch-all route for SPA - must be last
@app.get("/{full_path:path}")
async def serve_spa(full_path: str, request: Request):
    """Serve the SPA for all routes."""
    # Check if it's a static file request
    file_path = frontend_dir / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    # Otherwise serve index.html for SPA routing
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        content = index_path.read_text(encoding="utf-8")
        # Add CSP meta tag to prevent eval errors from browser extensions
        csp_meta = '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'self\' \'unsafe-inline\' https://fonts.googleapis.com; style-src \'self\' \'unsafe-inline\' https://fonts.googleapis.com; font-src \'self\' https://fonts.gstatic.com; connect-src \'self\' ws: wss:;">'
        content = content.replace("<head>", f"<head>\n    {csp_meta}")
        return HTMLResponse(content=content)
    return {"error": "Not found"}
