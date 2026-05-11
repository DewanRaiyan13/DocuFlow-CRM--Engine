"""Project schemas for API serialization."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.project import ProjectStatus, Sentiment


class ProjectCreate(BaseModel):
    title: str
    description: str | None = None
    case_number: str | None = None
    client_id: uuid.UUID


class ProjectUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    case_number: str | None = None
    status: ProjectStatus | None = None
    total_budget: float | None = None
    next_deadline: date | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    case_number: str | None
    status: ProjectStatus
    total_budget: float | None
    sentiment: Sentiment
    next_deadline: date | None
    llm_summary: str | None
    client_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
