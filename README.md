# QuizForge-AI (AI Tutor)

> **Mục tiêu:** Hệ thống trợ lý AI hỗ trợ sinh viên học tập thông qua việc tải tài liệu bài giảng, trích xuất kiến thức và tự động tạo câu hỏi trắc nghiệm kiểm tra chất lượng cao có dẫn chứng nguồn.

Dự án tham khảo kiến trúc từ [QuestGen-AI-Agent](https://github.com/cRED-f/QuestGen-AI-Agent) và phát triển theo mô hình phân công nhóm 3 người.

---

## 📚 Tài liệu Dự án

- 📋 [Kế hoạch triển khai chi tiết (IMPLEMENTATION_PLAN.md)](IMPLEMENTATION_PLAN.md)
- 🔌 [Hợp đồng API & JSON Schema (docs/API_CONTRACT.md)](docs/API_CONTRACT.md)
- 🏛️ [Kiến trúc hệ thống tổng quan (docs/ARCHITECTURE.md)](docs/ARCHITECTURE.md)
- 📝 [Biên bản chốt phạm vi MVP (docs/meeting-notes/decisions.md)](docs/meeting-notes/decisions.md)

---

## 👥 Phân công Vai trò Nhóm 3 người

| Thành viên | Vai trò | Khu vực phụ trách chính |
|---|---|---|
| **SV1** | RAG & Document Pipeline | `backend/documents.py`, `backend/ingestion.py` (Upload, trích xuất text, chia chunk, vector indexing) |
| **SV2** | Question Generation & Quality | `backend/generation.py`, `backend/exam_builder.py` (Prompt engineering, validate JSON Schema, chống trùng lặp) |
| **SV3** | UI & E2E Integration, QA | `app/(root)/chat/page.tsx`, `components/` (Frontend UI, review flow, điều phối API và kiểm thử tích hợp) |

---

## 🚀 Công nghệ Sử dụng

- **Frontend:** Next.js (App Router), React, Tailwind CSS, TypeScript
- **Backend:** FastAPI, Python 3.11+, Uvicorn, Pydantic v2
- **Vector & RAG:** LangChain / LlamaIndex, ChromaDB
- **LLM:** Google Gemini / OpenAI / Ollama
