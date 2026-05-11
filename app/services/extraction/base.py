"""
Abstract base for all file extractors.

Follows the Strategy pattern (Open/Closed Principle): add new file
types by implementing a new subclass – no existing code changes needed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ExtractionResult:
    """
    Standardized output from any extractor, regardless of file type.

    This data-class is the *contract* between the extraction layer
    and the ingestion pipeline.
    """

    raw_text: str = ""
    title: str | None = None
    date: datetime | None = None
    case_number: str | None = None
    page_count: int = 0
    metadata: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def is_successful(self) -> bool:
        return len(self.raw_text) > 0 and len(self.errors) == 0


class BaseExtractor(ABC):
    """
    Contract that every file-type extractor must fulfill.

    Subclasses implement ``extract()`` with type-specific parsing logic
    while the pipeline treats them uniformly through this interface.
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """File extensions this extractor handles (e.g., {'.pdf'})."""
        ...

    @abstractmethod
    async def extract(self, file_path: Path) -> ExtractionResult:
        """
        Parse the file and return structured data.

        Args:
            file_path: Absolute path to the file on disk.

        Returns:
            ExtractionResult with extracted text and metadata.
        """
        ...

    def can_handle(self, file_path: Path) -> bool:
        """Check whether this extractor supports the given file."""
        return file_path.suffix.lower() in self.supported_extensions
