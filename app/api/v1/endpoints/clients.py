"""
Client CRUD endpoints.

Clients are typically auto-populated from document ingestion
(via LLM-extracted parties), but can also be created manually.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models import Client, ClientStatus
from app.schemas.client import (
    ClientCreate,
    ClientListResponse,
    ClientRead,
    ClientUpdate,
)

router = APIRouter()


@router.get("/", response_model=ClientListResponse, summary="List all clients")
async def list_clients(
    status: ClientStatus | None = None,
    search: str | None = Query(None, min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    """
    Paginated client list with optional status and search filters.
    """
    query = select(Client)

    if status:
        query = query.where(Client.status == status)
    if search:
        query = query.where(Client.name.ilike(f"%{search}%"))

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginated results
    query = query.offset(skip).limit(limit).order_by(Client.created_at.desc())
    result = await db.execute(query)
    clients = result.scalars().all()

    return ClientListResponse(
        total=total,
        items=[ClientRead.model_validate(c) for c in clients],
    )


@router.post("/", response_model=ClientRead, status_code=201, summary="Create a client")
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_session),
):
    # For demo purposes, use a hardcoded owner_id (replace with auth)
    client = Client(
        **data.model_dump(),
        owner_id=uuid.uuid4(),  # TODO: Replace with authenticated user ID
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return ClientRead.model_validate(client)


@router.get("/{client_id}", response_model=ClientRead, summary="Get a client by ID")
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientRead.model_validate(client)


@router.patch("/{client_id}", response_model=ClientRead, summary="Update a client")
async def update_client(
    client_id: uuid.UUID,
    data: ClientUpdate,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    await db.flush()
    await db.refresh(client)
    return ClientRead.model_validate(client)


@router.delete("/{client_id}", status_code=204, summary="Delete a client")
async def delete_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    await db.delete(client)
