"""
Document Parsing and Validation Module for QuizForge-AI (Milestone M2 - SV1).
Production-grade implementation with strict validation, magic bytes verification,
Unicode NFC normalization for Vietnamese, and semantic layout preservation.
"""

import codecs
import hashlib
import logging
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Union

import pypdf
from pypdf import PasswordType
import docx
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from backend.schemas import ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024        # 20 MB max upload size
MAX_UNCOMPRESSED_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB max uncompressed ZIP bomb protection
SUPPORTED_EXTENSIONS = {"pdf", "docx", "txt"}
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class DocumentError(Exception):
    """Base exception for all document processing operations."""
    pass


class DocumentNotFoundError(DocumentError):
    """Raised when the specified file path does not exist on disk."""
    pass


class UnsupportedFileTypeError(DocumentError):
    """Raised when the file format or extension is not in the whitelist."""
    pass


class EmptyFileError(DocumentError):
    """Raised when the physical file is 0 bytes or has no textual content."""
    pass


class ScannedDocumentError(DocumentError):
    """Raised when a PDF contains pages but zero extractable text (likely scanned images)."""
    pass


class EncryptedFileError(DocumentError):
    """Raised when a file (e.g. PDF) is password-protected or encrypted."""
    pass


class CorruptedFileError(DocumentError):
    """Raised when a file cannot be parsed or unzipped due to structural corruption."""
    pass


class FileSizeLimitExceededError(DocumentError):
    """Raised when the uploaded file exceeds the allowed physical size limit."""
    pass


class ZipBombError(DocumentError):
    """Raised when an archive/DOCX expands beyond safe extraction limits."""
    pass


# ==============================================================================
# Text Cleaning & Normalization Utilities
# ==============================================================================

def normalize_vietnamese_text(text: str) -> str:
    """
    Standardizes text to Unicode NFC form, strips soft hyphens, and cleans typography glitches.
    Essential for Vietnamese RAG: prevents mismatches between decomposed (NFD)
    and precomposed (NFC) accents, which degrade vector embedding similarity.
    """
    if not text:
        return ""

    # 1. Chuẩn hóa xuống dòng TRƯỚC (để các regex bên dưới chỉ cần xử lý \n)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Soft hyphen: cuối dòng thì nối từ, còn lại thì xóa
    text = re.sub(r"\u00ad[ \t]*\n[ \t]*", "", text)
    text = text.replace("\u00ad", "")

    # 3. Unicode NFC
    text = unicodedata.normalize("NFC", text)

    # 4. Gạch nối cuối dòng: chỉ nối khi xuống dòng ĐƠN (không nuốt ngắt đoạn)
    text = re.sub(r"(\w+)-[ \t]*\n[ \t]*(\w+)", r"\1-\2", text)

    # 5. Gom khoảng trắng, giới hạn dòng trống
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def calculate_sha256(file_path: Path) -> str:
    """Calculates SHA-256 checksum in 8KB blocks to avoid memory overhead."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def _verify_magic_bytes(file_path: Path, expected_ext: str) -> None:
    """
    Validates file headers to prevent extension spoofing.
    - PDF: ISO 32000 allows %PDF- anywhere within the first 1024 bytes.
    - DOCX: Standard ZIP archive signature (PK\x03\x04).
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(1024)

        if expected_ext == "pdf":
            if b"%PDF-" not in header:
                raise CorruptedFileError(
                    f"File header mismatch: '{file_path.name}' does not contain a valid %PDF- signature in first 1KB."
                )
        elif expected_ext == "docx":
            if header.startswith(OLE_SIGNATURE):
                raise EncryptedFileError(
                    f"'{file_path.name}' bị khóa mật khẩu hoặc là định dạng .doc cũ. "
                    f"Hãy gỡ mật khẩu hoặc lưu lại thành .docx rồi tải lên."
                )
            if not header.startswith(b"PK\x03\x04"):
                raise CorruptedFileError(
                    f"File header mismatch: '{file_path.name}' does not have a valid DOCX/ZIP signature."
                )
    except OSError as e:
        raise DocumentError(f"Cannot read file header: {e}") from e


def _verify_docx_zip_safety(file_path: Path) -> None:
    """Guards against ZIP bomb attacks by verifying total uncompressed size."""
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > MAX_UNCOMPRESSED_SIZE_BYTES:
                raise ZipBombError(
                    f"DOCX archive '{file_path.name}' exceeds uncompressed expansion limit "
                    f"({total_uncompressed / (1024*1024):.1f}MB > {MAX_UNCOMPRESSED_SIZE_BYTES / (1024*1024):.0f}MB)."
                )
    except zipfile.BadZipFile as e:
        raise CorruptedFileError(f"Tệp DOCX hỏng hoặc không phải tệp ZIP/Office hợp lệ: {file_path.name}") from e


# ==============================================================================
# Parsers by Document Format
# ==============================================================================

def _parse_pdf(file_path: Path) -> list[ParsedPage]:
    """
    Parses PDF file page-by-page using pypdf.
    Properly handles password decryption, corrupted streams, and scanned PDFs.
    """
    pages: list[ParsedPage] = []
    try:
        reader = pypdf.PdfReader(str(file_path))

        # Check for password protection correctly via PasswordType
        if reader.is_encrypted:
            decrypt_result = reader.decrypt("")
            if decrypt_result == PasswordType.NOT_DECRYPTED:
                raise EncryptedFileError(
                    f"Tài liệu PDF '{file_path.name}' đã bị khóa bằng mật khẩu. Vui lòng gỡ mật khẩu trước khi tải lên."
                )

        num_pages = len(reader.pages)
        if num_pages == 0:
            raise EmptyFileError(f"PDF has 0 pages: {file_path.name}")

        empty_page_count = 0
        for idx, page in enumerate(reader.pages, start=1):
            try:
                raw_text = page.extract_text() or ""
            except Exception as e:
                logger.warning("Error extracting text on page %d of %s: %s", idx, file_path.name, e)
                raw_text = ""

            clean_text = normalize_vietnamese_text(raw_text)
            if clean_text:
                pages.append(ParsedPage(page=idx, text=clean_text))
            else:
                empty_page_count += 1

        if empty_page_count:
            logger.warning(
                "PDF '%s': %d/%d trang không có text layer",
                file_path.name, empty_page_count, num_pages,
            )

        # Distinguish between completely scanned/image PDF and valid PDF
        if not pages and num_pages > 0:
            raise ScannedDocumentError(
                f"Tài liệu PDF '{file_path.name}' không có lớp văn bản (text layer). "
                f"Đây có thể là tài liệu scan hoặc ảnh, cần qua xử lý OCR trước."
            )

    except DocumentError:
        raise
    except (pypdf.errors.PdfReadError, zipfile.BadZipFile) as e:
        raise CorruptedFileError(
            f"PDF hỏng hoặc không hợp lệ: {file_path.name}"
        ) from e
    except Exception as e:
        raise CorruptedFileError(
            f"Lỗi khi đọc file PDF '{file_path.name}': {type(e).__name__}: {e}"
        ) from e

    return pages


def _parse_docx(file_path: Path) -> list[ParsedPage]:
    """
    Parses DOCX preserving chronological document flow (interleaving
    paragraphs and tables in exact sequence as they appear in XML body).
    Correctly handles merged cells to prevent duplicate text, and preserves empty cells.
    """
    _verify_docx_zip_safety(file_path)

    try:
        doc = docx.Document(str(file_path))
        elements_text: list[str] = []

        for child in doc.element.body:
            if isinstance(child, CT_P):
                p = Paragraph(child, doc)
                p_text = normalize_vietnamese_text(p.text)
                if p_text:
                    elements_text.append(p_text)
            elif isinstance(child, CT_Tbl):
                tbl = Table(child, doc)
                row_strings = []
                for row in tbl.rows:
                    seen_tc = set()
                    cells = []
                    for cell in row.cells:
                        # Avoid duplicating text from horizontally merged cells (same _tc element)
                        if cell._tc in seen_tc:
                            continue
                        seen_tc.add(cell._tc)
                        cells.append(normalize_vietnamese_text(cell.text))

                    row_text = " | ".join(cells)
                    # Only append row if it contains at least some non-separator characters
                    if row_text.strip(" |"):
                        row_strings.append(row_text)

                if row_strings:
                    table_block = "[BẢNG BIỂU]:\n" + "\n".join(row_strings)
                    elements_text.append(table_block)

        full_text = "\n\n".join(elements_text).strip()
        if not full_text:
            raise EmptyFileError(f"Tài liệu DOCX không chứa văn bản: {file_path.name}")

        return [ParsedPage(page=None, text=full_text)]

    except DocumentError:
        raise
    except zipfile.BadZipFile as e:
        raise CorruptedFileError(
            f"Tệp DOCX hỏng hoặc không phải tệp ZIP/Office hợp lệ: {file_path.name}"
        ) from e
    except Exception as e:
        raise CorruptedFileError(
            f"Lỗi khi xử lý file DOCX '{file_path.name}': {type(e).__name__}: {e}"
        ) from e


def _decode_text_bytes(raw: bytes, filename: str) -> str:
    """
    Decodes plain text bytes with explicit UTF-16 BOM detection, UTF-8-SIG fallback,
    and CP1258 (Vietnamese Windows legacy).
    Prevents UTF-16 false-positive decoding of even-byte CP1258 files into Chinese mojibake.
    """
    # 1. Explicit UTF-16 BOM detection
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError as e:
            raise CorruptedFileError(f"File UTF-16 '{filename}' có BOM nhưng lỗi giải mã: {e}") from e

    # 2. Try UTF-8 (utf-8-sig transparently handles with/without BOM)
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    # 3. Fallback to CP1258 (Vietnamese Windows)
    try:
        return raw.decode("cp1258")
    except UnicodeDecodeError:
        pass

    raise CorruptedFileError(
        f"Không thể giải mã file TXT '{filename}'. Định dạng mã hóa không được hỗ trợ (chỉ nhận UTF-8, UTF-16 có BOM, CP1258)."
    )


def _parse_txt(file_path: Path) -> list[ParsedPage]:
    raw_bytes = file_path.read_bytes()
    decoded_text = _decode_text_bytes(raw_bytes, file_path.name)
    if "\x00" in decoded_text:
        raise CorruptedFileError(
            f"'{file_path.name}' chứa byte NUL, có vẻ là tệp nhị phân chứ không phải văn bản."
        )
    clean_text = normalize_vietnamese_text(decoded_text)
    if not clean_text:
        raise EmptyFileError(f"File TXT không chứa văn bản hợp lệ: {file_path.name}")

    return [ParsedPage(page=None, text=clean_text)]


# ==============================================================================
# Public API Entrypoint
# ==============================================================================

def parse_document(file_path: Union[str, Path]) -> ParsedDocument:
    """
    Primary ingestion entrypoint for Milestone 2 (SV1).
    Validates, extracts, normalizes, and packages lecture files into ParsedDocument.

    Order of verification:
    1. Existence check -> DocumentNotFoundError
    2. Whitelist extension check -> UnsupportedFileTypeError
    3. Empty file check (0 bytes) -> EmptyFileError
    4. Size limit check (>20MB) -> FileSizeLimitExceededError
    5. Magic bytes header check -> CorruptedFileError
    6. Content extraction -> ScannedDocumentError / EncryptedFileError / CorruptedFileError / EmptyFileError
    7. Pydantic validation -> ParsedDocument
    """
    path = Path(file_path)

    # 1. Existence check
    if not path.is_file():
        raise DocumentNotFoundError(f"Tài liệu không tồn tại: {path}")

    # 2. Whitelist extension check (clean without dot)
    suffix = path.suffix.lower()
    clean_ext = suffix.lstrip(".")
    if not clean_ext or clean_ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Định dạng tệp không được hỗ trợ: '{suffix}'. Hệ thống chỉ chấp nhận: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # 3. Empty file check (0 bytes)
    file_size = path.stat().st_size
    if file_size == 0:
        raise EmptyFileError(f"Tệp tin rỗng (0 bytes): '{path.name}'")

    # 4. Size limit check
    if file_size > MAX_FILE_SIZE_BYTES:
        raise FileSizeLimitExceededError(
            f"Dung lượng tệp ({file_size / (1024*1024):.2f}MB) vượt quá giới hạn cho phép (20MB): '{path.name}'"
        )

    # 5. Magic bytes check
    _verify_magic_bytes(path, clean_ext)

    # 6. Extract pages based on format
    if clean_ext == "pdf":
        pages = _parse_pdf(path)
    elif clean_ext == "docx":
        pages = _parse_docx(path)
    elif clean_ext == "txt":
        pages = _parse_txt(path)
    else:
        raise UnsupportedFileTypeError(f"Unsupported format: {clean_ext}")

    # Calculate post-cleaning character count
    total_characters = sum(len(p.text) for p in pages)
    if total_characters == 0:
        raise EmptyFileError(f"Tài liệu không có nội dung văn bản sau khi trích xuất: '{path.name}'")

    # 7. Package into ParsedDocument
    return ParsedDocument(
        file_name=path.name,
        file_type=clean_ext,
        sha256=calculate_sha256(path),
        pages=pages,
        total_characters=total_characters
    )
