# ARCHITECTURE & DESIGN OVERVIEW
# Dự án: QuizForge-AI (AI Tutor)

> **Mục tiêu:** Tài liệu mô tả kiến trúc tổng thể và luồng tương tác giữa các module cho dự án QuizForge-AI.

---

## 1. Kiến trúc Hệ thống Tổng thể

Hệ thống được xây dựng theo mô hình Client-Server hiện đại:

```
[ Frontend: Next.js (TypeScript, Tailwind CSS) ]
                   │
                   ▼ (REST API / JSON)
[ Backend: FastAPI (Python 3.11+) ]
   ├── Documents & Ingestion (SV1) ───► Vector Database (ChromaDB)
   ├── Question Generation (SV2)  ───► LLM Provider (Gemini / OpenAI / Ollama)
   └── Integration & Review API (SV3)
```

---

## 2. Phân chia Trách nhiệm & Module (SV1, SV2, SV3)

| Module | Thành viên phụ trách | File / Thư mục chính | Nhiệm vụ |
|---|---|---|---|
| **Retrieval & Documents** | **SV1** | `backend/documents.py`<br>`backend/ingestion.py` | Tiếp nhận file tải lên (.pdf, .docx, .txt), bóc tách văn bản, cắt đoạn (chunking), đánh chỉ mục vào Vector Store có gắn thẻ `course_id`. |
| **Generation & Quality** | **SV2** | `backend/generation.py`<br>`backend/exam_builder.py` | Nhận context trích xuất, xây dựng prompt kỹ thuật, gọi LLM, validate JSON Schema, kiểm tra tính hợp lệ của 4 phương án và đáp án đúng. |
| **Frontend & Integration** | **SV3** | `app/(root)/chat/page.tsx`<br>`components/` | Xây dựng giao diện upload, hiển thị danh sách câu hỏi `draft`, gắn nhãn trích dẫn nguồn, nút Duyệt / Bỏ qua, điều phối API và QA. |

---

## 3. Luồng Tương tác End-to-End (M1.1)

```text
[Người dùng]
     │ 1. Chọn Môn học & Upload File (.pdf/.docx/.txt)
     ▼
[Frontend UI]
     │ 2. POST /api/courses/{course_id}/documents
     ▼
[Backend - SV1]
     │ 3. Trích xuất text -> Cắt chunk -> Nhúng vector -> Lưu ChromaDB
     ▼
[Người dùng]
     │ 4. Nhập chủ đề & Bấm "Sinh câu hỏi"
     ▼
[Backend - SV1]
     │ 5. Tìm kiếm đoạn trích liên quan nhất trong Course (Similarity Search)
     ▼
[Backend - SV2]
     │ 6. Gửi Context + Prompt tới LLM -> Nhận câu hỏi
     │ 7. Validate Schema (4 đáp án, 1 đáp án đúng, kiểm tra rỗng/trùng)
     ▼
[Frontend UI]
     │ 8. Hiển thị câu hỏi ở trạng thái DRAFT kèm trích dẫn nguồn
     ▼
[Người dùng]
     │ 9. Đọc duyệt -> Bấm "Chấp nhận" (Accept) hoặc "Loại bỏ" (Reject)
     ▼
[Backend - SV3]
       10. Cập nhật trạng thái câu hỏi vào CSDL
```

---

## 4. Công nghệ Sử dụng
- **Frontend:** Next.js (App Router), React, Tailwind CSS, Lucide Icons.
- **Backend:** Python 3.11, FastAPI, Uvicorn, Pydantic v2.
- **RAG & Vector:** LangChain / LlamaIndex, ChromaDB.
- **LLM Support:** Google Gemini, OpenAI GPT, hoặc Ollama (Local LLM).
