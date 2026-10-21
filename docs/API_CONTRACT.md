# API CONTRACT & DATA SPECIFICATION
# Dự án: QuizForge-AI (AI Tutor)

> **Trạng thái:** Bản chốt hợp đồng dữ liệu cho Milestone M1  
> **Áp dụng cho:** SV1 (RAG), SV2 (Generation), SV3 (Frontend & Integration)

---

## 1. Chuẩn hóa Định dạng Response Chung

Mọi response trả về từ Backend API tuân theo cấu trúc wrapper chuẩn:

### Thành công:
```json
{
  "success": true,
  "data": {},
  "message": "Thao tác thành công"
}
```

### Thất bại:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Mô tả lỗi dễ hiểu cho người dùng",
    "details": {}
  }
}
```

---

## 2. Hệ thống Mã lỗi Chuẩn (Standard Error Codes - M1.3)

| Mã lỗi (`code`) | HTTP Status | Ý nghĩa & Tình huống xảy ra |
|---|---|---|
| `UNSUPPORTED_FILE_TYPE` | 400 | File tải lên không phải PDF, DOCX, TXT |
| `EMPTY_DOCUMENT` | 400 | File rỗng hoặc không trích xuất được ký tự nào |
| `FILE_TOO_LARGE` | 413 | Kích thước file vượt quá giới hạn (ví dụ > 20MB) |
| `COURSE_NOT_FOUND` | 404 | Môn học / Course ID không tồn tại |
| `NO_CONTEXT_FOUND` | 404 | Không tìm thấy đoạn trích phù hợp trong tài liệu để sinh câu hỏi |
| `MODEL_NOT_CONFIGURED` | 500 | Chưa cấu hình API Key cho LLM (OpenAI, Gemini, Ollama...) |
| `MODEL_TIMEOUT` | 504 | LLM mất quá nhiều thời gian phản hồi |
| `SCHEMA_VALIDATION_ERROR` | 422 / 502 | Kết quả từ LLM không khớp JSON Schema mục tiêu |
| `INTERNAL_SERVER_ERROR` | 500 | Lỗi server chưa xác định |

---

## 3. Schema Dữ liệu Mục tiêu cho Câu hỏi Trắc nghiệm (Target Question Schema - M1.2)

Một câu hỏi trắc nghiệm (`Question`) tuân thủ schema JSON nghiêm ngặt:

```json
{
  "id": "q_abc12345",
  "course_id": "course_cntt_01",
  "type": "mcq",
  "question": "Thuật toán tìm kiếm nhị phân có độ phức tạp thời gian trong trường hợp xấu nhất là gì?",
  "options": [
    {
      "id": "A",
      "text": "O(1)"
    },
    {
      "id": "B",
      "text": "O(n)"
    },
    {
      "id": "C",
      "text": "O(log n)"
    },
    {
      "id": "D",
      "text": "O(n^2)"
    }
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

### Ràng buộc dữ liệu (Validation Rules):
1. `options`: Phải chứa chính xác 4 lựa chọn, id duy nhất `["A", "B", "C", "D"]`.
2. `correct_option_id`: Bắt buộc phải là một trong các id của `options` (A, B, C hoặc D).
3. `status`: Nhận một trong các giá trị:
   - `draft`: Mới sinh, chờ người dùng duyệt.
   - `accepted`: Người dùng đã chấp nhận.
   - `rejected`: Người dùng loại bỏ.
4. `source_refs`: Danh sách nguồn trích dẫn; nếu không có trang cụ thể, trường `page` để `null`, tuyệt đối không tự bịa số trang.

---

## 4. Danh sách Endpoint API Thực tế (Endpoints Contract - M1.4)

### 4.1. Health Check
- **Endpoint:** `GET /api/health`
- **Response:**
  ```json
  {
    "status": "healthy",
    "timestamp": "2026-10-21T23:50:00Z"
  }
  ```

---

### 4.2. Upload & Ingest Tài liệu
- **Endpoint:** `POST /api/courses/{course_id}/documents`
- **Content-Type:** `multipart/form-data`
- **Request Body:**
  - `file`: File nhị phân (hỗ trợ `.pdf`, `.docx`, `.txt`)
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "doc_id": "doc_xyz789",
      "course_id": "course_cntt_01",
      "file_name": "Giao_trinh_CTDL_GT.pdf",
      "chunks_count": 35,
      "status": "indexed"
    },
    "message": "Tài liệu đã được tải lên và lập chỉ mục thành công."
  }
  ```

---

### 4.3. Lấy Danh sách Tài liệu của Môn học
- **Endpoint:** `GET /api/courses/{course_id}/documents`
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "data": [
      {
        "doc_id": "doc_xyz789",
        "file_name": "Giao_trinh_CTDL_GT.pdf",
        "uploaded_at": "2026-10-21T23:00:00Z",
        "chunks_count": 35
      }
    ]
  }
  ```

---

### 4.4. Sinh Câu hỏi Trắc nghiệm (Generate Questions)
- **Endpoint:** `POST /api/courses/{course_id}/questions/generate`
- **Content-Type:** `application/json`
- **Request Body:**
  ```json
  {
    "num_questions": 5,
    "topic": "Độ phức tạp thuật toán",
    "doc_ids": ["doc_xyz789"]
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "course_id": "course_cntt_01",
      "questions": [
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
          "explanation": "Tìm kiếm nhị phân có độ phức tạp O(log n).",
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
      ]
    },
    "message": "Đã sinh thành công 1 câu hỏi."
  }
  ```

---

### 4.5. Duyệt hoặc Loại bỏ Câu hỏi (Review Question)
- **Endpoint:** `PATCH /api/questions/{question_id}/review`
- **Content-Type:** `application/json`
- **Request Body:**
  ```json
  {
    "status": "accepted",
    "edited_question": null
  }
  ```
  *(Có thể gửi `edited_question` nếu người dùng chỉnh sửa nội dung/đáp án trước khi duyệt)*
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "question_id": "q_abc12345",
      "status": "accepted"
    },
    "message": "Trạng thái câu hỏi đã được cập nhật."
  }
  ```

---

## 5. Quy trình Kiểm thử Hợp đồng (Contract Testing - M1.5)
- SV1 và SV2 tạo unit test đảm bảo mọi dữ liệu xuất ra đều validate được với Pydantic model theo đúng schema trên.
- SV3 sử dụng mock data theo đúng định dạng này để dựng UI độc lập trong giai đoạn chờ API backend.
