"""
Unit tests for the ingestion pipeline.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.ingestion.pipeline import compute_file_hash, detect_mime_type


class TestFileUtilities:
    """Test hash computation and MIME type detection."""

    def test_compute_hash_consistency(self, tmp_path):
        """Same file content should produce the same hash."""
        f = tmp_path / "test.txt"
        f.write_text("Hello, DocuFlow!")
        hash1 = compute_file_hash(f)
        hash2 = compute_file_hash(f)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_different_files_different_hashes(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("File A")
        f2.write_text("File B")
        assert compute_file_hash(f1) != compute_file_hash(f2)

    def test_detect_mime_pdf(self):
        assert detect_mime_type(Path("contract.pdf")) == "application/pdf"

    def test_detect_mime_docx(self):
        mime = detect_mime_type(Path("proposal.docx"))
        assert "document" in mime or "officedocument" in mime

    def test_detect_mime_unknown(self):
        assert detect_mime_type(Path("file.xyz")) == "application/octet-stream"
