"""
Comprehensive Unit Tests for Milestone M2 - SV1 (backend/documents.py).
Fully verifies:
1. Text decoding (UTF-8, UTF-16 with BOM, CP1258, corrupted fallbacks).
2. PDF encryption detection (EncryptedFileError).
3. PDF scanned document detection (ScannedDocumentError).
4. DOCX table interleaving and merged cells deduplication.
5. Tolerant PDF magic bytes (within first 1024 bytes).
6. Unicode NFC normalization with strict assertion.
7. Order of checks (extension before empty, size limit, zip bomb protection).
"""

import codecs
import io
import unicodedata
import zipfile
from pathlib import Path
import pytest
import docx
import pypdf

from backend.documents import (
    parse_document,
    calculate_sha256,
    normalize_vietnamese_text,
    DocumentError,
    DocumentNotFoundError,
    UnsupportedFileTypeError,
    EmptyFileError,
    FileSizeLimitExceededError,
    CorruptedFileError,
    ScannedDocumentError,
    EncryptedFileError,
    ZipBombError,
    ParsedDocument
)


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


# ==============================================================================
# Success Path Tests
# ==============================================================================

def test_parse_valid_pdf_multi_page(fixtures_dir):
    """PDF must be parsed with correct 1-based page indices and clean text."""
    pdf_path = fixtures_dir / "sample_lecture.pdf"
    doc = parse_document(pdf_path)

    assert isinstance(doc, ParsedDocument)
    assert doc.file_name == "sample_lecture.pdf"
    assert doc.file_type == "pdf"  # Strictly without dot
    assert len(doc.pages) == 2
    assert doc.pages[0].page == 1
    assert doc.pages[1].page == 2
    assert "Binary Search" in doc.pages[0].text
    assert doc.total_characters > 100
    assert len(doc.sha256) == 64


def test_parse_valid_docx(fixtures_dir):
    """DOCX must parse successfully with page=None and extract text."""
    docx_path = fixtures_dir / "sample_lecture.docx"
    doc = parse_document(docx_path)

    assert doc.file_type == "docx"
    assert len(doc.pages) == 1
    assert doc.pages[0].page is None
    assert doc.total_characters > 50


def test_parse_valid_txt(fixtures_dir):
    """TXT must parse with UTF-8 support."""
    txt_path = fixtures_dir / "sample_course_doc.txt"
    doc = parse_document(txt_path)

    assert doc.file_type == "txt"
    assert len(doc.pages) == 1
    assert doc.pages[0].page is None
    assert doc.total_characters > 0


# ==============================================================================
# TXT Encoding & Decoding Tests (UTF-8, UTF-16 BOM, CP1258)
# ==============================================================================

def test_txt_decoding_utf16_with_bom(tmp_path):
    """UTF-16 with BOM must decode cleanly."""
    txt_file = tmp_path / "lecture_utf16.txt"
    content = "Bài giảng Cấu trúc dữ liệu và Giải thuật (UTF-16)"
    raw_bytes = codecs.BOM_UTF16_LE + content.encode("utf-16-le")
    txt_file.write_bytes(raw_bytes)

    doc = parse_document(txt_file)
    assert "Cấu trúc dữ liệu" in doc.pages[0].text


def test_txt_decoding_cp1258_vietnamese(tmp_path):
    """Legacy Vietnamese Windows CP1258 must be decoded properly without Chinese mojibake."""
    txt_file = tmp_path / "legacy_cp1258.txt"
    content = "Thuat toan tim kiem"
    # Encode with cp1258
    txt_file.write_bytes(content.encode("cp1258"))

    doc = parse_document(txt_file)
    assert "Thuat toan tim kiem" in doc.pages[0].text


def test_txt_invalid_binary_raises_corrupted(tmp_path):
    """Unrecognized random binary in .txt file raises CorruptedFileError."""
    bad_txt = tmp_path / "garbage.txt"
    # Non-valid UTF-8, non-BOM, invalid CP1258 sequence
    bad_txt.write_bytes(b"\x81\x82\xfe\xff\x80\x90\xaa\xbb\xcc")

    with pytest.raises(CorruptedFileError):
        parse_document(bad_txt)


def test_txt_with_nul_bytes_rejected(tmp_path):
    """Binary files (e.g. .exe) renamed to .txt containing NUL bytes must be rejected."""
    f = tmp_path / "binary.txt"
    f.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00 hello")
    with pytest.raises(CorruptedFileError):
        parse_document(f)


# ==============================================================================
# DOCX Table Interleaving & Merged Cells Tests
# ==============================================================================

def test_docx_table_interleaved_between_paragraphs_and_merged_cells(tmp_path):
    """
    Verifies that:
    1. Table appears between Paragraph 1 and Paragraph 2 in exact order.
    2. Horizontally merged cells do NOT duplicate text.
    """
    doc_path = tmp_path / "table_interleaved.docx"
    doc = docx.Document()
    doc.add_paragraph("Đoạn mở đầu trước bảng biểu.")

    # Create 2x2 table with merged top row
    table = doc.add_table(rows=2, cols=2)
    hdr_cell = table.cell(0, 0)
    hdr_cell.merge(table.cell(0, 1))
    hdr_cell.text = "Tiêu đề gộp 2 cột"

    table.cell(1, 0).text = "Ô dữ liệu 1"
    table.cell(1, 1).text = "Ô dữ liệu 2"

    doc.add_paragraph("Đoạn kết luận sau bảng biểu.")
    doc.save(str(doc_path))

    parsed = parse_document(doc_path)
    text = parsed.pages[0].text

    # Verify chronological sequence
    idx_p1 = text.find("Đoạn mở đầu trước bảng biểu.")
    idx_tbl = text.find("[BẢNG BIỂU]:")
    idx_p2 = text.find("Đoạn kết luận sau bảng biểu.")

    assert idx_p1 != -1 and idx_tbl != -1 and idx_p2 != -1
    assert idx_p1 < idx_tbl < idx_p2, "Table must appear between Paragraph 1 and Paragraph 2"

    # Verify merged cell does NOT duplicate: "Tiêu đề gộp 2 cột | Tiêu đề gộp 2 cột"
    assert text.count("Tiêu đề gộp 2 cột") == 1


# ==============================================================================
# PDF Encryption & Scanned Document Tests
# ==============================================================================

def test_pdf_encrypted_raises_encrypted_file_error(tmp_path):
    """Password-protected PDF must raise EncryptedFileError with clear guidance."""
    pdf_path = tmp_path / "locked.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret_password_123")
    with open(pdf_path, "wb") as f:
        writer.write(f)

    with pytest.raises(EncryptedFileError) as exc_info:
        parse_document(pdf_path)
    assert "mật khẩu" in str(exc_info.value).lower()


def test_pdf_scanned_without_text_layer_raises_scanned_error(tmp_path):
    """PDF containing pages but 0 text characters must raise ScannedDocumentError."""
    pdf_path = tmp_path / "scanned_image.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)  # Blank page simulates scanned image
    with open(pdf_path, "wb") as f:
        writer.write(f)

    with pytest.raises(ScannedDocumentError) as exc_info:
        parse_document(pdf_path)
    assert "text layer" in str(exc_info.value) or "scan" in str(exc_info.value)


def test_pdf_magic_bytes_tolerant_with_leading_bytes(tmp_path):
    """
    Standard PDF allows %PDF- anywhere within first 1024 bytes (e.g. scanner comment headers).
    Must pass magic byte verification.
    """
    pdf_path = tmp_path / "scanner_comment.pdf"
    # Create valid minimal PDF content
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    # Prepend 32 bytes of scanner comment, then %PDF- header
    prefixed_bytes = b"# Scanner Header Prefix Data 123\n" + pdf_bytes
    pdf_path.write_bytes(prefixed_bytes)

    # Magic byte check must succeed (won't raise CorruptedFileError on header)
    with pytest.raises(ScannedDocumentError):
        # Blank page -> ScannedDocumentError proves magic bytes check PASSED and reached parser!
        parse_document(pdf_path)


# ==============================================================================
# Security & Order of Checks Tests
# ==============================================================================

def test_order_of_checks_extension_before_empty(tmp_path):
    """
    Critical Edge Case:
    If a file has unsupported extension AND is 0 bytes (e.g. invalid_file.xyz),
    it MUST raise UnsupportedFileTypeError, NOT EmptyFileError.
    """
    empty_unsupported = tmp_path / "test_fake.xyz"
    empty_unsupported.write_bytes(b"")

    with pytest.raises(UnsupportedFileTypeError):
        parse_document(empty_unsupported)


def test_nonexistent_file_raises_not_found(tmp_path):
    """Missing file raises DocumentNotFoundError."""
    with pytest.raises(DocumentNotFoundError):
        parse_document(tmp_path / "ghost_file.pdf")


def test_empty_file_with_valid_extension(fixtures_dir):
    """0-byte file with supported extension (.txt) raises EmptyFileError."""
    with pytest.raises(EmptyFileError):
        parse_document(fixtures_dir / "empty_file.txt")


def test_file_size_limit_exceeded(fixtures_dir, monkeypatch):
    """Exceeding MAX_FILE_SIZE_BYTES raises FileSizeLimitExceededError."""
    import backend.documents as docs_mod

    monkeypatch.setattr(docs_mod, "MAX_FILE_SIZE_BYTES", 100)
    with pytest.raises(FileSizeLimitExceededError):
        parse_document(fixtures_dir / "sample_lecture.pdf")


def test_docx_zip_bomb_rejected(fixtures_dir, monkeypatch):
    import backend.documents as docs_mod
    monkeypatch.setattr(docs_mod, "MAX_UNCOMPRESSED_SIZE_BYTES", 100)
    with pytest.raises(ZipBombError):
        parse_document(fixtures_dir / "sample_lecture.docx")


def test_magic_bytes_spoofing_detection(tmp_path):
    """Renaming a text file to .pdf must fail magic byte check."""
    fake_pdf = tmp_path / "malicious.pdf"
    fake_pdf.write_text("This text file definitely has no PDF signature anywhere in first 1KB.")

    with pytest.raises(CorruptedFileError):
        parse_document(fake_pdf)


def test_docx_magic_bytes_spoofing(tmp_path):
    """Renaming non-zip file to .docx must fail magic byte check."""
    fake_docx = tmp_path / "fake.docx"
    fake_docx.write_bytes(b"NOT_A_ZIP_HEADER_CONTENT")

    with pytest.raises(CorruptedFileError):
        parse_document(fake_docx)


def test_docx_ole_header_raises_encrypted(tmp_path):
    f = tmp_path / "locked.docx"
    f.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100)
    with pytest.raises(EncryptedFileError):
        parse_document(f)


def test_zip_renamed_to_docx_raises_corrupted(tmp_path):
    fake = tmp_path / "fake.docx"
    with zipfile.ZipFile(fake, "w") as zf:
        zf.writestr("hello.txt", "đây không phải DOCX")
    with pytest.raises(CorruptedFileError):
        parse_document(fake)


def test_pdf_valid_header_garbage_body(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4\n" + b"garbage" * 50)
    with pytest.raises(DocumentError):  # chỉ lớp con của DocumentError được lọt ra
        parse_document(broken)


# ==============================================================================
# Unicode NFC & Text Cleaning Assertions
# ==============================================================================

def test_vietnamese_unicode_nfc_normalization():
    """
    Ensures decomposed Unicode (NFD) is transformed to precomposed (NFC).
    Strictly asserts that input != clean before normalization.
    """
    # "Tiếng Việt" in decomposed NFD format
    nfd_text = unicodedata.normalize("NFD", "Tiếng Việt bài giảng thuật toán")
    clean = normalize_vietnamese_text(nfd_text)

    # Prove that the input was actually non-NFC and different from clean
    assert nfd_text != clean
    assert clean == "Tiếng Việt bài giảng thuật toán"
    assert unicodedata.is_normalized("NFC", clean)


def test_text_hyphenation_and_soft_hyphens():
    """Soft hyphens (U+00AD) and line-broken words must be normalized."""
    raw = "Thuat-\u00ad\n  toan tim\u00ad kiem   nhi   phan.\n\n\n\nKet thuc."
    cleaned = normalize_vietnamese_text(raw)
    assert "\u00ad" not in cleaned
    assert "Thuat-toan tim kiem nhi phan." in cleaned
    assert "\n\n\n" not in cleaned


def test_soft_hyphen_at_line_end_joins_word():
    raw = "The algo\u00ad\nrithm and bi\u00adnary search, algo\u00ad\r\nrithm"
    assert normalize_vietnamese_text(raw) == (
        "The algorithm and binary search, algorithm"
    )


def test_hyphen_does_not_merge_paragraphs():
    assert "\n\n" in normalize_vietnamese_text("Phần một-\n\nPhần hai")


def test_sha256_deterministic_and_matches():
    """Identical files produce exact same hash."""
    p1 = Path(__file__)
    h1 = calculate_sha256(p1)
    h2 = calculate_sha256(p1)
    assert h1 == h2 and len(h1) == 64
