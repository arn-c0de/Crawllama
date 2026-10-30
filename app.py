"""FastAPI application for CrawlLama - Production-ready API."""
import logging
import os
from contextlib import asynccontextmanager

import dotenv
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.middleware import install_middleware
from api.routers.admin import router as admin_router
from api.routers.config import router as config_router
from api.routers.memory import router as memory_router
from api.routers.osint import router as osint_router
from api.routers.plugins import router as plugins_router
from api.routers.query import router as query_router
from api.routers.session import router as session_router
from api.routers.system import router as system_router
from api.security_config import API_KEY, hash_api_key_for_logging  # noqa: F401 - re-exported
from api.startup import (  # noqa: F401 - _grant_bootstrap_admin_role re-exported
    _grant_bootstrap_admin_role,
    load_app_config,
    shutdown_event,
    startup_event,
)
from core.api_key_manager import get_api_key_manager
from core.audit_logger import get_audit_logger
from core.csrf_manager import get_csrf_manager
from core.rbac_manager import get_rbac_manager

# Load environment variables
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crawllama")

# Version constant (single source of truth in _version.py)
from _version import __version__ as VERSION  # noqa: E402 - needs logger configured first

# Initialize CSRF Manager
csrf_manager = get_csrf_manager()
logger.info("CSRF protection initialized")

# Initialize RBAC Manager
rbac_manager = get_rbac_manager()
logger.info("RBAC (Role-Based Access Control) initialized")

# Initialize Audit Logger
audit_logger = get_audit_logger()
logger.info("Audit logging initialized")

# Initialize API Key Manager (for rotation support)
api_key_manager = get_api_key_manager()
logger.info("API key rotation manager initialized")

# Initialize FastAPI app


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup/shutdown logic (modern replacement for on_event hooks)."""
    await startup_event(app)
    yield
    await shutdown_event()


app = FastAPI(
    title="CrawlLama API",
    description="AI-powered web research agent with multi-hop reasoning",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Mount static files for web interface
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("Static files mounted successfully")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

config = load_app_config()

install_middleware(app)


# Mount extracted endpoint routers
app.include_router(admin_router)
app.include_router(osint_router)
app.include_router(plugins_router)
app.include_router(session_router)
app.include_router(memory_router)
app.include_router(query_router)
app.include_router(config_router)
app.include_router(system_router)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    # SECURITY: Do not leak the exception class name to clients; it aids
    # fingerprinting of internals. The full detail is in the server logs.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn

    # Bind host is loopback by default; if overridden via env, the DEV_MODE
    # loopback guard (_enforce_dev_mode_loopback_only) refuses to start when
    # DEV_MODE is also enabled on a network-reachable host.
    uvicorn.run(
        "app:app",
        host=os.getenv("CRAWLLAMA_HOST") or os.getenv("HOST") or "127.0.0.1",
        port=int(os.getenv("CRAWLLAMA_PORT") or os.getenv("PORT") or "8000"),
        reload=False,
        log_level="info"
    )
