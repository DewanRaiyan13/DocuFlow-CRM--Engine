"""Client schemas for API serialization."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.client import ClientStatus


class ClientCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    company: str | None = None
    notes: str | None = None


class ClientUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    company: str | None = None
    notes: str | None = None
    status: ClientStatus | None = None


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    company: str | None
    notes: str | None
    status: ClientStatus
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime


class ClientListResponse(BaseModel):
    total: int
    items: list[ClientRead]
