"""
Project model – groups documents under a client engagement.

Stores extracted "soft" metadata such as total budget, sentiment,
and deadline – all populated automatically by the LLM enrichment step.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    ForeignKey, String, Text, Numeric, Date,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

import enum


class ProjectStatus(str, enum.Enum):
    PROPOSAL = "proposal"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class Sentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    # ── Core ───────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    case_number: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True,
    )

    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="project_status", create_constraint=True),
        default=ProjectStatus.PROPOSAL,
        index=True,
    )

    # ── LLM-extracted "soft" data ──────────────────────────────────
    total_budget: Mapped[float | None] = mapped_column(Numeric(12, 2))
    sentiment: Mapped[Sentiment] = mapped_column(
        SAEnum(Sentiment, name="sentiment", create_constraint=True),
        default=Sentiment.UNKNOWN,
    )
    next_deadline: Mapped[date | None] = mapped_column(Date)
    llm_summary: Mapped[str | None] = mapped_column(Text)

    # ── Foreign keys ───────────────────────────────────────────────
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────
    client: Mapped["Client"] = relationship(back_populates="projects")  # noqa: F821
    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Project {self.title} [{self.case_number}]>"
