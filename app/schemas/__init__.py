"""Pydantic schemas for API request/response serialization."""

from app.schemas.client import (  # noqa: F401
    ClientCreate,
    ClientListResponse,
    ClientRead,
    ClientUpdate,
)
from app.schemas.document import (  # noqa: F401
    BulkUploadResponse,
    DocumentRead,
    DocumentUploadResponse,
)
from app.schemas.intelligence import StaleLeadReport  # noqa: F401
from app.schemas.project import (  # noqa: F401
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
