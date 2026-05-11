"""
Stale Lead Detector – Relationship Intelligence module.

Scans the database for clients whose ``last_activity_at`` is older
than the configured threshold (default: 14 days). Clients matching
the criteria are flagged with ``status = STALE`` and included in
the report.

This can be called on-demand via the API or scheduled as a periodic
Celery beat task.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Client, ClientStatus, Project
from app.schemas.intelligence import StaleClientRecord, StaleLeadReport

logger = logging.getLogger(__name__)
settings = get_settings()


class StaleLeadDetector:
    """
    Detect and flag clients with no recent activity.

    Usage::

        detector = StaleLeadDetector(session)
        report = await detector.run()
    """

    def __init__(
        self,
        session: AsyncSession,
        threshold_days: int | None = None,
    ) -> None:
        self._session = session
        self._threshold_days = threshold_days or settings.STALE_LEAD_THRESHOLD_DAYS

    async def run(self, auto_flag: bool = True) -> StaleLeadReport:
        """
        Execute the stale-lead scan.

        Args:
            auto_flag: If True, automatically update matching clients'
                       status to ``STALE``.

        Returns:
            A StaleLeadReport with all detected stale clients.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self._threshold_days
        )

        # ── Query stale clients with project counts ────────────────
        stmt = (
            select(
                Client,
                func.count(Project.id).label("project_count"),
            )
            .outerjoin(Project, Project.client_id == Client.id)
            .where(
                Client.last_activity_at < cutoff,
                Client.status.notin_([
                    ClientStatus.ARCHIVED,
                    ClientStatus.STALE,
                ]),
            )
            .group_by(Client.id)
            .order_by(Client.last_activity_at.asc())
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        stale_records: list[StaleClientRecord] = []
        stale_ids: list = []

        now = datetime.now(timezone.utc)

        for client, project_count in rows:
            days_inactive = (now - client.last_activity_at).days
            stale_records.append(
                StaleClientRecord(
                    client_id=client.id,
                    client_name=client.name,
                    company=client.company,
                    last_activity_at=client.last_activity_at,
                    days_inactive=days_inactive,
                    project_count=project_count,
                )
            )
            stale_ids.append(client.id)

        # ── Auto-flag stale clients ────────────────────────────────
        if auto_flag and stale_ids:
            await self._session.execute(
                update(Client)
                .where(Client.id.in_(stale_ids))
                .values(status=ClientStatus.STALE)
            )
            await self._session.commit()
            logger.info("Flagged %d clients as STALE.", len(stale_ids))

        report = StaleLeadReport(
            threshold_days=self._threshold_days,
            generated_at=now,
            total_stale=len(stale_records),
            stale_clients=stale_records,
        )

        return report
