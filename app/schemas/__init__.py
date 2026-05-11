"""Pydantic schemas for API request/response serialization."""

from app.schemas.client import (  # noqa: F401
    ClientCreate, ClientRead, ClientUpdate, ClientListResponse,
)
from app.schemas.project import (  # noqa: F401
    ProjectCreate, ProjectRead, ProjectUpdate,
)
from app.schemas.document import (  # noqa: F401
    DocumentRead, DocumentUploadResponse, BulkUploadResponse,
)
from app.schemas.intelligence import StaleLeadReport  # noqa: F401
