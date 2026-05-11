"""Schemas for the Relationship Intelligence endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class StaleClientRecord(BaseModel):
    client_id: uuid.UUID
    client_name: str
    company: str | None
    last_activity_at: datetime
    days_inactive: int
    project_count: int


class StaleLeadReport(BaseModel):
    threshold_days: int
    generated_at: datetime
    total_stale: int
    stale_clients: list[StaleClientRecord]
