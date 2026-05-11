"""
API dependencies – injectable utilities for route handlers.
"""

from __future__ import annotations

from app.db.session import get_db


async def get_session() -> AsyncSession:
    """Alias for get_db – used in Depends() for readability."""
    async for session in get_db():
        yield session
