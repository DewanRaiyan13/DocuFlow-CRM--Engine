"""
InteractionLog model – audit trail for client touchpoints.

Every document ingestion, manual note, or email integration creates
a log entry. This powers the "Stale Lead" detection: if no interaction
exists within the configured threshold, the client is flagged.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class InteractionType(str, enum.Enum):
    DOCUMENT_INGESTED = "document_ingested"
    NOTE_ADDED = "note_added"
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    MEETING = "meeting"
    STATUS_CHANGE = "status_change"


class InteractionLog(TimestampMixin, Base):
    __tablename__ = "interaction_logs"

    interaction_type: Mapped[InteractionType] = mapped_column(
        SAEnum(
            InteractionType,
            name="interaction_type",
            create_constraint=True,
        ),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)

    # ── Foreign keys ───────────────────────────────────────────────
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────
    client: Mapped["Client"] = relationship(  # noqa: F821
        back_populates="interactions",
    )

    def __repr__(self) -> str:
        return f"<InteractionLog {self.interaction_type.value} for client={self.client_id}>"
