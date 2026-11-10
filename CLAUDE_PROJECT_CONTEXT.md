# QUIZFORGE-AI (AI TUTOR) — TECHNICAL REPORT & CODE HANDOFF
> **Target Audience:** Claude / Senior AI Engineer / Code Reviewer  
> **Timestamp:** November 2026  
> **Repository:** QuizForge-AI (based on `cRED-f/QuestGen-AI-Agent` under MIT License)  
> **Current Status:** Completed M0 (Baseline), M1 (API Contract & Schemas), and M2.A (Document Parsing & Validation - SV1). 35/35 Unit Tests PASSED.

---

## 1. THÔNG TIN DỰ ÁN & MÔ HÌNH PHÂN CÔNG 3 SINH VIÊN (12 TUẦN)

- **Tên dự án:** QuizForge-AI (AI Tutor – Tạo câu hỏi trắc nghiệm kiểm tra từ tài liệu bài giảng có trích dẫn nguồn).
- **Mã nguồn nền tảng (Base Repo):** `https://github.com/cRED-f/QuestGen-AI-Agent` (Giấy phép mã nguồn mở MIT).
- **Mục tiêu hệ thống (MVP):**
  1. Quản lý tài liệu theo từng môn học (`course_id`) để cách ly ngữ cảnh.
  2. Bóc tách văn bản chuẩn xác từ PDF, DOCX, TXT kèm theo số trang vật lý (`page`) để dẫn nguồn.
  3. Cắt đoạn (Chunking) có window overlap và lập chỉ mục Vector DB (ChromaDB).
  4. Sử dụng LLM (Google Gemini API / OpenAI / Ollama) để sinh câu hỏi trắc nghiệm 4 lựa chọn (A, B, C, D) theo **Thang đo nhận thức Bloom** và mức độ khó (`easy`, `medium`, `hard`).
  5. Đảm bảo câu hỏi bám sát tài liệu bài giảng (Grounding), kèm theo giải thích chi tiết và trích dẫn nguồn gốc (`file_name`, `page`, `snippet`).
  6. Giao diện Next.js hỗ trợ quy trình duyệt câu hỏi tương tác (Review Flow: `draft` -> `accepted` / `rejected`).

- **Phân công trách nhiệm 3 sinh viên (Lộ trình 12 tuần):**
  - Hai phân hệ **M2 (Xử lý Tài liệu & RAG)** và **M3 (Sinh câu hỏi bằng AI & Kiểm định)** là hai phần khó nhất nên **cả 3 sinh viên đều cùng tham gia lập trình lõi**:
    - **Sinh viên 1 (SV1):**
      - M2.A: Tiếp nhận file, kiểm tra Magic bytes / OLE header, bóc tách text đa định dạng, chuẩn hóa tiếng Việt Unicode NFC (`backend/documents.py`).
      - M3.A: Ghép nối ngữ cảnh (Context Injection) và Prompt Engineering chống ảo giác (Grounding).
    - **Sinh viên 2 (SV2):**
      - M2.B: Thuật toán cắt đoạn văn bản (Text Chunking) có sliding window overlap và lưu trữ Vector DB ChromaDB (`backend/ingestion.py`).
      - M3.B: Tích hợp Async LLM API (Google Gemini), cơ chế chịu lỗi Retry / Exponential Backoff.
    - **Sinh viên 3 (SV3 - Trưởng nhóm):**
      - M2.C: Tìm kiếm ngữ nghĩa cách ly theo môn học (`course-scoped retrieval`) và đóng gói nguồn trích dẫn (`source_refs`).
      - M3.C: Bộ lọc kiểm định chất lượng (Quality Gatekeeper) xác thực JSON Schema, thuật toán lọc câu trùng lặp (Deduplication).
      - M4: Lập trình giao diện Next.js, xây dựng Review Flow (`Accept`/`Reject`), kết nối API toàn hệ thống.

---

## 2. CÁC ĐIỂM ĐÃ SỬA VÀ TỐI ƯU SO VỚI BẢN NHÁP BAN ĐẦU

Nhóm áp dụng nguyên tắc **"Kế thừa có chọn lọc theo từng bước (Incremental Adoption)"**, phân tích kỹ các lỗi biên và hoàn thiện tầng Ingestion:

| Tiêu chí | Bản nháp ban đầu | Bản hoàn thiện (`backend/documents.py`) | Giá trị kỹ thuật thực tế |
|---|---|---|---|
| **Khôi phục bắt lỗi PDF & DOCX** | Gói chung lỗi vào `CorruptedFileError`, vô tình nuốt mất các lỗi con chuyên biệt. | Đặt `except DocumentError: raise` ở đầu mọi khối parser trước khi bắt `Exception`. | Đảm bảo `EncryptedFileError`, `ScannedDocumentError`, `EmptyFileError` không bị nuốt. |
| **Giải mã TXT & Chặn file nhị phân** | Dùng danh sách thử encoding; `utf-16` nuốt byte chẵn của `cp1258`; `cp1258` nuốt file nhị phân (`.exe`). | Nhận diện UTF-16 qua BOM (`BOM_UTF16_LE/BE`), thử `utf-8-sig`, fallback `cp1258`; **chặn ngay file chứa byte `\x00` (NUL byte)**. | Loại bỏ chữ Hán rác và chặn file nhị phân đội lốt `.txt`. |
| **PDF mã hóa mật khẩu** | Dùng `try...except` quanh `reader.decrypt("")` nhưng `pypdf` trả về `PasswordType.NOT_DECRYPTED` (0). | So sánh tường minh: `if decrypt_result == PasswordType.NOT_DECRYPTED: raise EncryptedFileError`. | Phân biệt chính xác giữa file bị khóa mật khẩu và file hỏng. |
| **Bảng DOCX ô gộp (merged cells)** | Lặp chữ ở các ô gộp ngang; lọc `strip()` làm lệch cấu trúc cột. | Khử lặp ô gộp qua con trỏ XML `cell._tc`, giữ ô trống để bảo toàn số cột. | Tránh nhân bản text gây nhiễu cho Vector Search. |
| **Khoan dung Magic Bytes PDF** | Chỉ so sánh 5 bytes đầu (`startswith(b"%PDF-")`). | Kiểm tra `b"%PDF-" in header[:1024]` theo đúng chuẩn ISO 32000. | Chấp nhận các file PDF có comment/header từ máy scan. |
| **Nhận diện DOCX khóa & .doc cũ** | Chỉ kiểm tra chữ ký ZIP `PK\x03\x04`. | Nhận diện header `OLE_SIGNATURE` (`\xd0\xcf\x11...`) ném `EncryptedFileError`. | Hướng dẫn người dùng gỡ pass hoặc lưu lại sang .docx chuẩn. |
| **Soft Hyphen & Chuẩn hóa NFC** | Xóa `\u00ad` nhưng để lại `\n` làm gãy từ; regex `\s*` nuốt mất dấu ngắt đoạn. | Chuẩn hóa `\r\n` trước; regex `[ \t]*\n[ \t]*` nối từ ngắt dòng đơn, giữ nguyên `\n\n`. | Chuẩn hóa triệt để tiếng Việt trước khi tạo Vector Embeddings. |
| **Cảnh báo Zip Bomb** | Không kiểm tra dung lượng uncompressed. | Kiểm tra kích thước khai báo trong header ZIP (`sum(info.file_size)` > 100MB). | Cảnh báo sớm các file nén bất thường. *(Lưu ý: kiểm tra dựa trên header)* |

---

## 3. GIỚI HẠN KỸ THUẬT ĐÃ BIẾT (KNOWN LIMITATIONS)
Nhóm chủ động ghi nhận các giới hạn kỹ thuật của phiên bản MVP để báo cáo trung thực với Giảng viên:
1. **Định dạng DOCX:** Hiện tại chỉ bóc tách các đoạn văn bản chính (`Paragraphs`) và bảng biểu (`Tables`) trong `body`. Chưa đọc phần Header/Footer, Footnotes, Endnotes, Text Boxes và bảng lồng nhau (nested tables).
2. **Định dạng TXT:** Hỗ trợ chuẩn xác các bảng mã UTF-8 (có/không BOM), UTF-16 (có BOM) và Windows CP1258. Các bảng mã cổ như TCVN3 (ABC) hoặc VNI không được tự động chuyển đổi.
3. **Định dạng PDF:** Hệ thống không tích hợp OCR nặng. Tài liệu PDF scan hoàn toàn không có text layer sẽ bị từ chối (`ScannedDocumentError`). Đối với tài liệu scan hỗn hợp (chỉ một số trang là ảnh), hệ thống vẫn xử lý các trang có chữ và ghi log cảnh báo (`logger.warning`).
4. **Ngắt dòng giữa câu (Line-wrapping):** Việc xuống dòng giữa câu trong PDF được giữ nguyên theo dòng vật lý, logic ghép câu hoàn chỉnh (de-hyphenation / flow restoration) được chuyển giao cho SV2 xử lý tại tầng Chunking.

---

## 4. SCHEMAS HỢP ĐỒNG LIÊN MODULE (backend/schemas.py)

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class BloomLevel(str, Enum):
    REMEMBER = "remember"       # Nhận biết / Ghi nhớ
    UNDERSTAND = "understand"   # Thông hiểu
    APPLY = "apply"             # Vận dụng
    ANALYZE = "analyze"         # Phân tích
    EVALUATE = "evaluate"       # Đánh giá
    CREATE = "create"           # Sáng tạo

class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class OptionItem(BaseModel):
    id: str = Field(description="Option identifier: 'A', 'B', 'C', 'D'")
    text: str = Field(min_length=1, description="Option display text")

class SourceReference(BaseModel):
    doc_id: str = Field(description="Associated document ID")
    file_name: str = Field(description="Original file name")
    page: Optional[int] = Field(default=None, description="Page number if available")
    snippet: str = Field(description="Relevant extracted text segment")

class TargetMCQuestion(BaseModel):
    id: str
    course_id: str
    type: str = "mcq"
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND
    question: str = Field(min_length=5)
    options: list[OptionItem] = Field(min_length=4, max_length=4)
    correct_option_id: str
    explanation: str = Field(min_length=5)
    source_refs: list[SourceReference] = Field(default_factory=list)
    status: str = "draft"  # draft, accepted, rejected

# ==============================================================================
# Hợp đồng bàn giao giữa SV1 -> SV2 -> SV3 trong Milestone M2
# ==============================================================================

class ParsedPage(BaseModel):
    page: Optional[int] = Field(default=None, description="Số trang (1-based) cho PDF, None cho DOCX/TXT")
    text: str = Field(description="Nội dung văn bản sạch")

class ParsedDocument(BaseModel):
    """Output của SV1 (Parsing & Validation) -> Input bàn giao cho SV2 (Chunking)"""
    file_name: str = Field(description="Tên file tải lên")
    file_type: str = Field(description="Định dạng: 'pdf', 'docx', hoặc 'txt'")
    sha256: str = Field(description="Mã băm SHA-256 để chống trùng file")
    pages: list[ParsedPage] = Field(description="Danh sách các trang/phần đã bóc tách")
    total_characters: int = Field(ge=1, description="Tổng số ký tự hợp lệ sau làm sạch")

class DocumentChunk(BaseModel):
    """Output của SV2 (Chunking & Indexing) -> Input lưu ChromaDB & SV3 (Retrieval)"""
    chunk_id: str = Field(description="ID định danh duy nhất của chunk")
    doc_id: str = Field(description="ID của tài liệu cha")
    course_id: str = Field(description="ID môn học để cách ly dữ liệu")
    file_name: str = Field(description="Tên file gốc")
    page: Optional[int] = Field(default=None, description="Số trang bài giảng")
    content: str = Field(min_length=10, description="Nội dung văn bản của đoạn cắt")
    chunk_index: int = Field(ge=0, description="Thứ tự xuất hiện của đoạn trong tài liệu")

class RetrievalResult(BaseModel):
    """Output của SV3 (Course-Scoped Retrieval) -> Input cho Prompting M3"""
    course_id: str
    query: str
    matches: list[SourceReference]
```

---

## 5. TOÀN VĂN MÃ NGUỒN BACKEND/DOCUMENTS.PY (SV1)

```python
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
MAX_UNCOMPRESSED_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB max uncompressed ZIP bomb protection (based on header size)
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
    """Raised when a file (e.g. PDF/DOCX) is password-protected or encrypted."""
    pass


class CorruptedFileError(DocumentError):
    """Raised when a file cannot be parsed or unzipped due to structural corruption."""
    pass


class FileSizeLimitExceededError(DocumentError):
    """Raised when the uploaded file exceeds the allowed physical size limit."""
    pass


class ZipBombError(DocumentError):
    """Raised when an archive/DOCX expands beyond safe extraction limits (header check)."""
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
    - DOCX: Recognizes OLE encrypted header or standard PK\x03\x04 ZIP signature.
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
    """Guards against ZIP bomb attacks by verifying total uncompressed size from header."""
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
                        if cell._tc in seen_tc:
                            continue
                        seen_tc.add(cell._tc)
                        cells.append(normalize_vietnamese_text(cell.text))

                    row_text = " | ".join(cells)
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
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError as e:
            raise CorruptedFileError(f"File UTF-16 '{filename}' có BOM nhưng lỗi giải mã: {e}") from e

    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

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
    path = Path(file_path)

    # 1. Kiểm tra tồn tại
    if not path.is_file():
        raise DocumentNotFoundError(f"Tài liệu không tồn tại: {path}")

    # 2. Kiểm tra định dạng hỗ trợ (loại bỏ dấu chấm)
    suffix = path.suffix.lower()
    clean_ext = suffix.lstrip(".")
    if not clean_ext or clean_ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Định dạng tệp không được hỗ trợ: '{suffix}'. Hệ thống chỉ chấp nhận: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # 3. Kiểm tra tệp rỗng
    file_size = path.stat().st_size
    if file_size == 0:
        raise EmptyFileError(f"Tệp tin rỗng (0 bytes): '{path.name}'")

    # 4. Kiểm tra giới hạn 20MB
    if file_size > MAX_FILE_SIZE_BYTES:
        raise FileSizeLimitExceededError(
            f"Dung lượng tệp ({file_size / (1024*1024):.2f}MB) vượt quá giới hạn cho phép (20MB): '{path.name}'"
        )

    # 5. Kiểm tra chữ ký Magic bytes (khoan dung trong 1KB đầu cho PDF)
    _verify_magic_bytes(path, clean_ext)

    # 6. Bóc tách theo từng định dạng
    if clean_ext == "pdf":
        pages = _parse_pdf(path)
    elif clean_ext == "docx":
        pages = _parse_docx(path)
    elif clean_ext == "txt":
        pages = _parse_txt(path)
    else:
        raise UnsupportedFileTypeError(f"Unsupported format: {clean_ext}")

    total_characters = sum(len(p.text) for p in pages)
    if total_characters == 0:
        raise EmptyFileError(f"Tài liệu không có nội dung văn bản sau khi trích xuất: '{path.name}'")

    return ParsedDocument(
        file_name=path.name,
        file_type=clean_ext,
        sha256=calculate_sha256(path),
        pages=pages,
        total_characters=total_characters
    )
```

---

## 6. BẰNG CHỨNG KIỂM THỬ THỰC TẾ (RAW PYTEST OUTPUT — 35/35 PASSED)

```text
============================= test session starts =============================
platform win32 -- Python 3.12.0, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\AD\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: D:\AI_sinh_cau_hoi
plugins: anyio-4.15.1
collecting ... collected 35 items

tests/test_contract.py::test_target_schema_valid_creation PASSED         [  2%]
tests/test_contract.py::test_target_schema_rejects_non_4_options PASSED  [  5%]
tests/test_contract.py::test_target_schema_rejects_mismatched_correct_option PASSED [  8%]
tests/test_contract.py::test_target_schema_rejects_duplicate_options PASSED [ 11%]
tests/test_contract.py::test_questgen_adapter_successful_mapping_with_bloom PASSED [ 14%]
tests/test_contract.py::test_bloom_taxonomy_mapping_levels PASSED        [ 17%]
tests/test_contract.py::test_questgen_adapter_error_when_correct_answer_not_in_options PASSED [ 20%]
tests/test_documents.py::test_parse_valid_pdf_multi_page PASSED          [ 22%]
tests/test_documents.py::test_parse_valid_docx PASSED                    [ 25%]
tests/test_documents.py::test_parse_valid_txt PASSED                     [ 28%]
tests/test_documents.py::test_txt_decoding_utf16_with_bom PASSED         [ 31%]
tests/test_documents.py::test_txt_decoding_cp1258_vietnamese PASSED      [ 34%]
tests/test_documents.py::test_txt_invalid_binary_raises_corrupted PASSED [ 37%]
tests/test_documents.py::test_txt_with_nul_bytes_rejected PASSED         [ 40%]
tests/test_documents.py::test_docx_table_interleaved_between_paragraphs_and_merged_cells PASSED [ 42%]
tests/test_documents.py::test_pdf_encrypted_raises_encrypted_file_error PASSED [ 45%]
tests/test_documents.py::test_pdf_scanned_without_text_layer_raises_scanned_error PASSED [ 48%]
tests/test_documents.py::test_pdf_magic_bytes_tolerant_with_leading_bytes PASSED [ 51%]
tests/test_documents.py::test_order_of_checks_extension_before_empty PASSED [ 54%]
tests/test_documents.py::test_nonexistent_file_raises_not_found PASSED   [ 57%]
tests/test_documents.py::test_empty_file_with_valid_extension PASSED     [ 60%]
tests/test_documents.py::test_file_size_limit_exceeded PASSED            [ 62%]
tests/test_documents.py::test_docx_zip_bomb_rejected PASSED              [ 65%]
tests/test_documents.py::test_magic_bytes_spoofing_detection PASSED      [ 68%]
tests/test_documents.py::test_docx_magic_bytes_spoofing PASSED           [ 71%]
tests/test_documents.py::test_docx_ole_header_raises_encrypted PASSED    [ 74%]
tests/test_documents.py::test_zip_renamed_to_docx_raises_corrupted PASSED [ 77%]
tests/test_documents.py::test_pdf_valid_header_garbage_body PASSED       [ 80%]
tests/test_documents.py::test_vietnamese_unicode_nfc_normalization PASSED [ 82%]
tests/test_documents.py::test_text_hyphenation_and_soft_hyphens PASSED   [ 85%]
tests/test_documents.py::test_soft_hyphen_at_line_end_joins_word PASSED  [ 88%]
tests/test_documents.py::test_hyphen_does_not_merge_paragraphs PASSED    [ 91%]
tests/test_documents.py::test_sha256_deterministic_and_matches PASSED    [ 94%]
tests/test_m2_contracts.py::test_fixture_files_exist_and_readable PASSED [ 97%]
tests/test_m2_contracts.py::test_m2_handoff_contract_validation PASSED   [100%]

============================= 35 passed in 0.69s ==============================
```

---

## 7. ĐIỀU PHỐI VÀ THỐNG NHẤT HỢP ĐỒNG TRƯỚC KHI LÀM M3

### Vấn đề vị trí trích dẫn cho DOCX và TXT (`page=None`):
- Với PDF, `page` là số nguyên (1, 2, ...), phục vụ dẫn nguồn chính xác theo từng trang slide/giáo trình.
- Với DOCX và TXT, tài liệu không có trang vật lý nên `page=None`.
- **Khuyến nghị kiến trúc bàn giao cho SV2 & SV3:** Giữ nguyên schema hiện tại (`page: Optional[int] = None`) để hoàn thành MVP đúng tiến độ. Trong phiên bản nâng cao (M2.B+), nhóm có thể bổ sung trường `section: Optional[str] = None` vào `ParsedPage` và `SourceReference` để ghi nhận tiêu đề mục gần nhất (Heading 1/2) của DOCX mà không làm vỡ schema cốt lõi.

---

## 8. NHIỆM VỤ TIẾP THEO CHO CLAUDE (SV2: CHUNKING & INGESTION)

Yêu cầu hỗ trợ tiếp tục dự án:
1. **Module mục tiêu:** Viết file `backend/ingestion.py` cho **Sinh viên 2 (SV2)**.
2. **Dữ liệu đầu vào (Input):** Nhận `ParsedDocument` do hàm `parse_document()` của SV1 trả về.
3. **Nhiệm vụ cụ thể của SV2 cần Claude code tiếp:**
   - Xây dựng thuật toán cắt đoạn (Chunking) có sliding window overlap (ví dụ `chunk_size=600`, `chunk_overlap=120`), xử lý việc nối câu bị gãy giữa dòng trong PDF.
   - Giữ toàn vẹn metadata bài giảng cho từng đoạn cắt: `course_id`, `doc_id`, `file_name`, và quan trọng nhất là `page` (để sau này trích dẫn).
   - Đóng gói danh sách đầu ra thành `list[DocumentChunk]` đúng chuẩn Pydantic schema trong `backend/schemas.py`.
   - Viết pipeline nhúng (Embedding) và lưu trữ vector vào ChromaDB phân vùng theo `course_id`.
   - Viết bài kiểm thử `tests/test_ingestion.py` kiểm chứng 100% pass.
