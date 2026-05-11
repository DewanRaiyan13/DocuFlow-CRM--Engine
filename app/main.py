"""
DocuFlow-CRM – FastAPI Application Entry Point.

This module wires together the API routers, middleware, and lifecycle
events (DB pool init, file watcher startup).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.v1.router import api_router
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Startup / Shutdown lifecycle.

    On startup:
      - Verify DB connectivity.
      - (Optionally) launch the file watcher in a background thread.
    On shutdown:
      - Dispose the async engine connection pool.
    """
    # ── Startup ────────────────────────────────────────────────────
from app.db.session import async_session_factory
    async with async_session_factory() as session:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))

    yield

    # ── Shutdown ───────────────────────────────────────────────────
    await engine.dispose()


def create_application() -> FastAPI:
    """Application factory – keeps module-level import side-effects minimal."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Headless, document-driven CRM engine for freelancers. "
            "Zero manual data entry – drop files, get structured records."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
