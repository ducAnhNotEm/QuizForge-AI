"""
Tests for Milestone M2 Inter-Module Hand-off Contracts and Fixture Files.
Ensures SV1, SV2, and SV3 have valid, verified sample structures.
"""

import json
from pathlib import Path
import pytest
from backend.schemas import (
    ParsedPage,
    ParsedDocument,
    DocumentChunk,
    RetrievalResult,
    SourceReference
)


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


def test_fixture_files_exist_and_readable(fixtures_dir):
    """Verify all real sample files exist on disk for M2 testing."""
    pdf_file = fixtures_dir / "sample_lecture.pdf"
    docx_file = fixtures_dir / "sample_lecture.docx"
    txt_file = fixtures_dir / "sample_course_doc.txt"
    empty_file = fixtures_dir / "empty_file.txt"
    invalid_file = fixtures_dir / "invalid_file.xyz"

    assert pdf_file.exists() and pdf_file.stat().st_size > 0
    assert docx_file.exists() and docx_file.stat().st_size > 0
    assert txt_file.exists() and txt_file.stat().st_size > 0
    assert empty_file.exists() and empty_file.stat().st_size == 0
    assert invalid_file.exists() and invalid_file.stat().st_size > 0


def test_m2_handoff_contract_validation(fixtures_dir):
    """Verify sample JSON hand-off data strictly conforms to M2 Pydantic models."""
    sample_path = fixtures_dir / "sample_m2_handoff.json"
    with open(sample_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Test SV1 output structure
    sv1_out = ParsedDocument(**data["sv1_output_sample"])
    assert sv1_out.file_type == "pdf"
    assert len(sv1_out.pages) == 2
    assert sv1_out.pages[0].page == 1

    # 2. Test SV2 output structure
    chunks = [DocumentChunk(**item) for item in data["sv2_output_sample"]]
    assert len(chunks) == 2
    assert chunks[0].course_id == "course_cntt"
    assert chunks[0].chunk_index == 0

    # 3. Test SV3 output structure
    retrieval_out = RetrievalResult(**data["sv3_output_sample"])
    assert retrieval_out.course_id == "course_cntt"
    assert len(retrieval_out.matches) == 1
    assert isinstance(retrieval_out.matches[0], SourceReference)
    assert retrieval_out.matches[0].page == 1
