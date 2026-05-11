"""
Aggregated v1 API router.

All endpoint modules are mounted here with descriptive tags for
auto-generated OpenAPI documentation.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    clients,
    documents,
    health,
    intelligence,
    projects,
)

api_router = APIRouter()

api_router.include_router(
    health.router, prefix="/health", tags=["Health"],
)
api_router.include_router(
    clients.router, prefix="/clients", tags=["Clients"],
)
api_router.include_router(
    projects.router, prefix="/projects", tags=["Projects"],
)
api_router.include_router(
    documents.router, prefix="/documents", tags=["Documents"],
)
api_router.include_router(
    intelligence.router, prefix="/intelligence", tags=["Intelligence"],
)
