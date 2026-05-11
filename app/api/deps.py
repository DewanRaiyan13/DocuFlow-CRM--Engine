"""
API dependencies – injectable utilities for route handlers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db  # noqa: F401


async def get_session() -> AsyncIterator[AsyncSession]:
    """Alias for get_db – used in Depends() for readability."""
    async for session in get_db():
        yield session
