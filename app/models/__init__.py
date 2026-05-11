"""
Models package – re-exports all ORM models for Alembic auto-detection
and convenient importing.
"""

from app.models.base import Base, TimestampMixin  # noqa: F401
from app.models.client import Client, ClientStatus  # noqa: F401
from app.models.document import Document, DocumentType, ProcessingStatus  # noqa: F401
from app.models.interaction import InteractionLog, InteractionType  # noqa: F401
from app.models.project import Project, ProjectStatus, Sentiment  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Client",
    "ClientStatus",
    "Project",
    "ProjectStatus",
    "Sentiment",
    "Document",
    "DocumentType",
    "ProcessingStatus",
    "InteractionLog",
    "InteractionType",
]
