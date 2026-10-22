# API CONTRACT & DATA SPECIFICATION
# Dự án: QuizForge-AI (AI Tutor)

> **Mục tiêu:** Bản hợp đồng giao tiếp giữa các module (M1), được **đối chiếu trực tiếp với mã nguồn gốc của [QuestGen-AI-Agent](https://github.com/cRED-f/QuestGen-AI-Agent)** (`backend/app.py`, `backend/generation.py`, `backend/customization.py`).  
> **Trạng thái:** Chốt duyệt bởi SV1, SV2, SV3.

---

## 1. Luồng Tương Tác Hệ Thống (Workflow - M1.1)

```text
[Người dùng / SV3 Frontend]
      │
      ├─ 1. Chọn / Tạo Môn học (Course)
      │     POST /api/courses hoặc GET /api/courses
      │
      ├─ 2. Tải tài liệu học tập (.pdf, .docx, .txt)
      │     POST /api/courses/{course_id}/documents
      │     └── SV1 (RAG): Bóc tách text -> Chunking -> Vector Index
      │
      ├─ 3. Yêu cầu sinh câu hỏi trắc nghiệm
      │     POST /api/courses/{course_id}/questions/generate  (MVP Target Endpoint)
      │     (Hoặc luồng QuestGen gốc: POST /api/threads -> POST .../generations)
      │     └── SV1: Tìm context liên quan
      │     └── SV2: Prompt LLM -> Nhận output -> Validate Schema
      │
      ├─ 4. Hiển thị danh sách câu hỏi DRAFT kèm nguồn trích dẫn
      │     UI hiển thị 4 lựa chọn, đáp án, giải thích, tên file & trang trích dẫn
      │
      └─ 5. Người dùng xem xét và Review
            PATCH /api/questions/{question_id}/review
            └── Trạng thái chuyển thành: "accepted" hoặc "rejected"
```

---

## 2. Đối Chiếu Endpoint Thực Tế Giữa QuestGen Và MVP Target (M1.4)

| Nghiệp vụ | Endpoint gốc QuestGen (`backend/app.py`) | Endpoint mục tiêu MVP QuizForge-AI | Ghi chú & Chiến lược chuyển tiếp |
|---|---|---|---|
| **Health Check** | `GET /api/health` (L295, L359) | `GET /api/health` | Giữ nguyên 100% |
| **Danh sách Môn học** | `GET /api/courses` (L364) | `GET /api/courses` | Giữ nguyên |
| **Tạo Môn học** | `POST /api/courses` (L370) | `POST /api/courses` | Body: `{"name": str, "description": str}` |
| **Tải lên Tài liệu** | `POST /api/courses/{course_id}/documents` (L563) | `POST /api/courses/{course_id}/documents` | Multipart form `file`. Giữ nguyên logic trích xuất PDF/DOCX/TXT của SV1 |
| **Tìm kiếm Đoạn trích** | `GET /api/courses/{course_id}/search?q=...` (L693) | `GET /api/courses/{course_id}/search` | Phục vụ kiểm thử RAG của SV1 |
| **Sinh Câu hỏi** | `POST /api/threads/{thread_id}/generations` (L1988)<br>*(Kèm cơ chế Blueprint & Job queue)* | **Cách 1 (MVP Wrapper):**<br>`POST /api/courses/{course_id}/questions/generate`<br><br>**Cách 2 (Gốc):**<br>Qua Thread API | SV2 cung cấp hàm adapter bọc luồng sinh câu hỏi trả về ngay danh sách câu hỏi chuẩn hóa |
| **Duyệt Câu hỏi (Review)** | `PUT /api/threads/{thread_id}/generations/{job_id}/questions/{question_id}/review` (L2125) | `PATCH /api/questions/{question_id}/review` | Body chuẩn: `{"status": "accepted" \| "rejected"}` |

---

## 3. Ánh Xạ Schema Câu Hỏi Trắc Nghiệm (Schema Mapping - M1.2)

### 3.1. Cấu trúc câu hỏi gốc của QuestGen (`backend/generation.py` - L54)
```python
class GeneratedQuestion(BaseModel):
    stem: str                       # Nội dung câu hỏi
    options: list[str]              # Mảng tối đa 4 chuỗi text phương án
    correct_answer: str             # Chuỗi text trùng khớp 1 trong các options
    explanation: str                # Giải thích
    source_ids: list[str]           # ID các đoạn tài liệu nguồn (chunk ids)
```

### 3.2. Cấu trúc câu hỏi mục tiêu (Target Schema MVP)
```json
{
  "id": "q_abc12345",
  "course_id": "course_cntt_01",
  "type": "mcq",
  "question": "Thuật toán tìm kiếm nhị phân có độ phức tạp thời gian trong trường hợp xấu nhất là gì?",
  "options": [
    {"id": "A", "text": "O(1)"},
    {"id": "B", "text": "O(n)"},
    {"id": "C", "text": "O(log n)"},
    {"id": "D", "text": "O(n^2)"}
  ],
  "correct_option_id": "C",
  "explanation": "Tìm kiếm nhị phân chia đôi không gian tìm kiếm ở mỗi bước nên độ phức tạp là O(log n).",
  "source_refs": [
    {
      "doc_id": "doc_xyz789",
      "file_name": "Giao_trinh_CTDL_GT.pdf",
      "page": 42,
      "snippet": "Thuật toán tìm kiếm nhị phân trên mảng đã sắp xếp có thời gian thực thi là O(log n)."
    }
  ],
  "status": "draft"
}
```

### 3.3. Bảng quy tắc chuyển đổi (Adapter Rules):
| Trường Target (QuizForge) | Trường Gốc (QuestGen) | Quy tắc chuyển đổi (Adapter Logic) |
|---|---|---|
| `id` | `assessment_questions.id` | Giữ nguyên mã ID chuỗi |
| `type` | `kind` | Mặc định `"mcq"` cho câu hỏi trắc nghiệm |
| `question` | `stem` | Ánh xạ trực tiếp từ `stem` |
| `options` (`list[OptionItem]`) | `options` (`list[str]`) | Chuyển đổi: `[{"id": "A", "text": opt[0]}, {"id": "B", "text": opt[1]}, ...]` |
| `correct_option_id` | `correct_answer` | Tìm index của `correct_answer` trong `options`: `chr(65 + index)` (`"A"`, `"B"`, `"C"`, `"D"`) |
| `explanation` | `explanation` | Ánh xạ trực tiếp |
| `source_refs` | `source_ids` | Tra cứu `source_ids` qua bảng `document_units` để lấy `doc_id`, `file_name`, `page`, `snippet`. Nếu chưa có page thì để `null` |
| `status` | `review.decision` | Ánh xạ: `pending` $\rightarrow$ `draft`; `approved` $\rightarrow$ `accepted`; `rejected` $\rightarrow$ `rejected` |

---

## 4. Đặc Tả Mã Lỗi và Xử Lý Ngoại Lệ (Error Handling - M1.3)

Đối chiếu với các ngoại lệ thực tế được bắt trong `backend/app.py`:

| Mã lỗi (`error.code`) | HTTP Status trong QuestGen | Trường hợp xảy ra | Cách ứng xử của Frontend (SV3) |
|---|---|---|---|
| `UNSUPPORTED_FILE_TYPE` | 422 | `documents.validate_payload` bắt lỗi đuôi file không thuộc PDF/DOCX/TXT | Hiển thị thông báo: "Chỉ hỗ trợ file .pdf, .docx, .txt" |
| `EMPTY_DOCUMENT` | 422 | File 0 byte hoặc không bóc tách được ký tự nào | Hiển thị thông báo: "Tài liệu rỗng hoặc không thể đọc nội dung" |
| `FILE_TOO_LARGE` | 422 | File vượt quá giới hạn `MAX_UPLOAD` (30MB) | Thông báo file vượt quá dung lượng |
| `COURSE_NOT_FOUND` | 404 | `fetch_or_404(conn, "courses", course_id)` | Điều hướng người dùng về trang chọn môn học |
| `MODEL_NOT_CONFIGURED` | 500 | `require_model(settings)` hoặc thiếu API Key nhà cung cấp | Thông báo: "Chưa cấu hình API Key cho AI Model" |
| `MODEL_TIMEOUT` | 504 / 500 | Quá thời gian gọi LLM | Hiển thị nút "Thử lại (Retry)" |
| `SCHEMA_VALIDATION_ERROR` | 422 / 502 | LLM sinh JSON sai định dạng, thiếu 4 đáp án hoặc đáp án đúng không khớp | Tự động thử sinh lại (regenerate) hoặc thông báo lỗi |

---

## 5. Quy Chuẩn Đóng Gói Phản Hồi (Response Wrapper)

### Thành công:
```json
{
  "success": true,
  "data": { ... },
  "message": "Thành công"
}
```

### Thất bại:
```json
{
  "success": false,
  "error": {
    "code": "EMPTY_DOCUMENT",
    "message": "File tải lên không có nội dung chữ để trích xuất.",
    "details": {}
  }
}
```
