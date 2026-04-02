"""
Céal Web Application Factory

Creates and configures the FastAPI app with Jinja2 templates,
static files, and route registration.

Interview talking point:
    "I used the application factory pattern so the web layer
    is independently testable — the same pattern Django and
    Flask use for production applications."
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

# Template and static file paths (relative to this file)
_WEB_DIR = Path(__file__).parent
_TEMPLATE_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    from src.models.database import init_db
    await init_db()
    yield


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    app = FastAPI(
        title="Céal — Career Signal Engine",
        description="AI-powered job matching and resume tailoring pipeline",
        version="2.1.0",
        lifespan=lifespan,
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Register route modules
    from src.web.routes import applications, apply, dashboard, demo, jobs
    app.include_router(dashboard.router)
    app.include_router(jobs.router)
    app.include_router(applications.router)
    app.include_router(apply.router)
    app.include_router(demo.router)

    return app


# Default app instance for uvicorn
app = create_app()
