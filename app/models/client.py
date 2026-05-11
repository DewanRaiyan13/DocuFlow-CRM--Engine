"""
Client model – external contacts / leads tracked by the CRM.

The ``last_activity_at`` column powers the Stale Lead detector:
any document ingestion or interaction log updates this timestamp.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

import enum


class ClientStatus(str, enum.Enum):
    """Lifecycle stages a client can be in."""
    LEAD = "lead"
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    # ── Core fields ────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    company: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    status: Mapped[ClientStatus] = mapped_column(
        SAEnum(ClientStatus, name="client_status", create_constraint=True),
        default=ClientStatus.LEAD,
        index=True,
    )

    # ── Stale-lead tracking ────────────────────────────────────────
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Foreign keys ───────────────────────────────────────────────
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────
    owner: Mapped["User"] = relationship(back_populates="clients")  # noqa: F821
    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        back_populates="client",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    interactions: Mapped[list["InteractionLog"]] = relationship(  # noqa: F821
        back_populates="client",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Client {self.name} ({self.status.value})>"
