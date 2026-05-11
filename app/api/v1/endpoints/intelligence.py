"""
Intelligence endpoints – Stale Lead detection and relationship insights.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.intelligence import StaleLeadReport
from app.services.intelligence.stale_detector import StaleLeadDetector

router = APIRouter()


@router.get(
    "/stale-leads",
    response_model=StaleLeadReport,
    summary="Detect stale leads",
)
async def get_stale_leads(
    threshold_days: int = Query(14, ge=1, le=365),
    auto_flag: bool = Query(True),
    db: AsyncSession = Depends(get_session),
):
    """
    Scan for clients with no activity in the last N days.

    - **threshold_days**: Inactivity cutoff (default: 14).
    - **auto_flag**: If true, automatically set status to STALE.
    """
    detector = StaleLeadDetector(db, threshold_days=threshold_days)
    return await detector.run(auto_flag=auto_flag)


@router.post(
    "/stale-leads/scan",
    response_model=dict,
    status_code=202,
    summary="Trigger async stale-lead scan",
)
async def trigger_stale_lead_scan():
    """
    Dispatch the stale-lead detection as an async Celery task.
    Useful for scheduled or manual bulk scans.
    """
    from app.workers.tasks import detect_stale_leads_task

    result = detect_stale_leads_task.delay()
    return {
        "task_id": result.id,
        "status": "dispatched",
        "message": "Stale lead scan queued. Check task status for results.",
    }
