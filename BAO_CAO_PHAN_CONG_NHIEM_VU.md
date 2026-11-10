# BÁO CÁO PHÂN CÔNG NHIỆM VỤ ĐỀ TÀI ĐỒ ÁN (LỘ TRÌNH 12 TUẦN)
## HỆ THỐNG TRỢ LÝ HỌC TẬP THÔNG MINH TỰ ĐỘNG TẠO CÂU HỎI TRẮC NGHIỆM TỪ TÀI LIỆU (QUIZFORGE-AI)

---

- **Tên đề tài:** QuizForge-AI (AI Tutor – Tự động tạo câu hỏi trắc nghiệm kiểm tra từ bài giảng có trích dẫn nguồn)
- **Giảng viên hướng dẫn:** *[Thầy/Cô điền tên Giảng viên hướng dẫn]*
- **Nhóm sinh viên thực hiện:** 03 thành viên
  - **Sinh viên 1 (SV1):** *[Họ và tên - MSSV]*
  - **Sinh viên 2 (SV2):** *[Họ và tên - MSSV]*
  - **Sinh viên 3 (SV3):** *[Họ và tên - MSSV]* *(Trưởng nhóm)*
- **Thời lượng thực hiện:** 12 tuần (Kỳ làm Đồ án / Khóa luận tốt nghiệp)
- **Mã nguồn nền tảng tham khảo:** QuestGen-AI-Agent (Giấy phép mã nguồn mở MIT)

---

## 1. MỤC TIÊU VÀ NGUYÊN TẮC PHÂN CÔNG ĐỀ TÀI

### 1.1. Mục tiêu cốt lõi của hệ thống (MVP)
1. **Không gian học tập theo môn học (Course-scoped):** Quản lý tài liệu theo từng môn học/chủ đề để tránh rò rỉ hoặc lẫn lộn kiến thức giữa các học phần.
2. **Tiếp nhận & Xử lý tài liệu đa định dạng:** Tải lên bài giảng dạng PDF, DOCX, TXT; bóc tách nội dung chính xác kèm theo số trang và vị trí văn bản.
3. **Truy xuất ngữ nghĩa chính xác (RAG Pipeline):** Cắt đoạn (chunking), tạo vector nhúng (embeddings) và tìm kiếm đoạn trích phù hợp nhất trong tài liệu của môn học bằng Vector Database (ChromaDB).
4. **Sinh câu hỏi trắc nghiệm bằng LLM:** Tạo câu hỏi 4 lựa chọn (A, B, C, D) có 1 đáp án đúng, lời giải thích chi tiết và trích dẫn nguồn gốc (tên file, số trang, trích đoạn) để minh bạch hóa kiến thức.
5. **Quy trình duyệt câu hỏi tương tác (Review Flow):** Câu hỏi sinh ra ở trạng thái nháp (`draft`), người học/giảng viên có thể xem trước, chấp nhận (`accept`) đưa vào ngân hàng đề hoặc loại bỏ (`reject`).

### 1.2. Định hướng và Nguyên tắc phân công công việc
> ⚠️ **Quy tắc cốt lõi của nhóm:** Hai phân hệ **M2 (Xử lý Tài liệu & RAG Pipeline)** và **M3 (Sinh câu hỏi bằng AI & Đảm bảo Chất lượng)** là hai phân hệ **khó nhất, phức tạp nhất và chiếm phần lớn khối lượng kỹ thuật của đồ án**.  
> Do đó, nhóm **không giao khoán M2 hay M3 cho một người làm riêng lẻ**, mà **cả 3 sinh viên đều tham gia lập trình trực tiếp vào lõi M2 và M3**, chia thành 3 phân mảng kỹ thuật chuyên biệt để cùng nhau nghiên cứu, bổ trợ và kiểm soát rủi ro kỹ thuật.

---

## 2. MA TRẬN PHÂN CHIA TRÁCH NHIỆM THEO MILESTONES (RACI MATRIX)

| Milestone | Nội dung công việc | Sinh viên 1 (SV1) | Sinh viên 2 (SV2) | Sinh viên 3 (SV3) |
|:---:|---|:---:|:---:|:---:|
| **M0** | Khảo sát nền tảng, thiết lập môi trường, chạy baseline | Tham gia cài đặt | Tham gia cài đặt | **Chủ trì điều phối** |
| **M1** | Thiết kế Kiến trúc, Hợp đồng API & Schemas Pydantic | Xây dựng Schema Dữ liệu | Xây dựng Schema Câu hỏi | **Tài liệu hóa & Test contract** |
| **M2** | **Xử lý Tài liệu & RAG Pipeline (Phần khó - Cả 3 cùng làm)** | **Phụ trách M2.A**<br>*(File Parsing & Validation)* | **Phụ trách M2.B**<br>*(Chunking & Vector DB)* | **Phụ trách M2.C**<br>*(Course Retrieval & Citation)* |
| **M3** | **Sinh câu hỏi & Kiểm soát AI (Phần khó - Cả 3 cùng làm)** | **Phụ trách M3.A**<br>*(Context Injection & Prompt)* | **Phụ trách M3.B**<br>*(LLM Integration & Resilience)* | **Phụ trách M3.C**<br>*(Quality Gatekeeper & Dedup)* |
| **M4** | **Giao diện Next.js & Tích hợp End-to-End** | Phối hợp luồng Upload UI | Phối hợp cấu hình AI UI | **Chủ trì xây dựng UI & API** |
| **M5** | **Kiểm thử E2E, Tinh chỉnh, Viết Báo cáo & Demo** | Kiểm thử dữ liệu & Viết báo cáo | Đánh giá AI & Viết báo cáo | **Chủ trì tổng hợp, Slide & Demo** |

---

## 3. PHÂN CHIA CHI TIẾT 2 PHÂN HỆ CỐT LÕI (M2 & M3) CHO 3 SINH VIÊN

### 📌 PHÂN HỆ M2: XỬ LÝ TÀI LIỆU & RAG PIPELINE (Chia 3 người)

| Phân hệ con | Thành viên phụ trách | Nhiệm vụ kỹ thuật chuyên sâu | Tệp mã nguồn & Unit Test |
|---|:---:|---|---|
| **M2.A: Input Validation & File Parser** | **SV1** | • Lập trình bộ bóc tách văn bản chuẩn xác cho PDF (kèm đánh số trang), Word (.docx) và Plain Text (.txt).<br>• Xử lý kiểm tra dung lượng (< 20MB), chặn file 0-byte (`empty_file.txt`), chặn phần mở rộng lạ.<br>• Tính toán mã băm SHA-256 để chống tải lên tài liệu trùng lặp. | `backend/documents.py`<br>`backend/course_tools.py`<br>`tests/test_documents.py`<br>`tests/fixtures/` |
| **M2.B: Chunking Strategy & Vector Storage** | **SV2** | • Thiết kế thuật toán cắt đoạn văn bản (Text Chunker) có độ gối đầu (sliding window overlap) hợp lý để bảo toàn ngữ nghĩa bài giảng.<br>• Xây dựng pipeline nhúng (Embedding) và lưu trữ vector vào ChromaDB.<br>• Gắn nhãn metadata chi tiết cho từng chunk (`course_id`, `doc_id`, `page`, `chunk_id`). | `backend/ingestion.py`<br>`tests/test_ingestion.py` |
| **M2.C: Course-Scoped Retrieval & Citation** | **SV3** | • Xây dựng hàm tìm kiếm tương đồng ngữ nghĩa (Similarity Search) có bộ lọc cách ly tuyệt đối theo môn học (`course_id`).<br>• Lọc ngưỡng tương đồng (threshold score) để loại bỏ các đoạn văn bản không liên quan.<br>• Đóng gói danh sách trích dẫn nguồn (`source_refs`: tên file, số trang, trích đoạn gốc) đính kèm kết quả. | `backend/retrieval.py`<br>`tests/test_retrieval.py`<br>`tests/test_m2_contracts.py` |

---

### 📌 PHÂN HỆ M3: SINH CÂU HỎI BẰNG AI & KIỂM ĐỊNH CHẤT LƯỢNG (Chia 3 người)

| Phân hệ con | Thành viên phụ trách | Nhiệm vụ kỹ thuật chuyên sâu | Tệp mã nguồn & Unit Test |
|---|:---:|---|---|
| **M3.A: Context Injection & Prompt Engineering** | **SV1** | • Tiếp nhận kết quả từ retrieval, làm sạch và đóng gói vào cấu trúc Context đưa vào LLM.<br>• Thiết kế kỹ thuật Prompt Engineering chuyên sâu (System prompt + User prompt) buộc mô hình bám sát tài liệu bài giảng (Grounding), chống bịa đặt kiến thức (Hallucination).<br>• Yêu cầu mô hình sinh giải thích vì sao đáp án đúng và vì sao 3 phương án còn lại sai. | `backend/exam_context.py`<br>`backend/prompts.py`<br>`tests/test_prompt_context.py` |
| **M3.B: LLM Integration & Resilience Pipeline** | **SV2** | • Tích hợp các LLM Provider: Google Gemini API (ưu tiên chính), OpenAI GPT và Local LLM (Ollama).<br>• Xây dựng cơ chế gọi API bất đồng bộ (Async), quản lý token limit.<br>• Xử lý chống nghẽn và chịu lỗi: Cơ chế Retry với Exponential Backoff khi API mạng bị ngắt quãng hoặc gặp rate-limit.<br>• Tối ưu tham số mô hình (`temperature`, `top_p`) chuyên dụng cho sinh đề trắc nghiệm. | `backend/generation.py`<br>`backend/llm_client.py`<br>`tests/test_llm_resilience.py` |
| **M3.C: Quality Gatekeeper & Deduplication** | **SV3** | • Xây dựng bộ lọc kiểm định chất lượng đầu ra: Validate nghiêm ngặt JSON Schema bằng Pydantic v2 (chặn lỗi JSON méo, thiếu trường).<br>• Kiểm tra logic đề thi: Đúng 4 phương án độc lập (A, B, C, D), không có lựa chọn trùng nhau, đáp án đúng phải thuộc danh sách lựa chọn.<br>• Thuật toán lọc câu hỏi trùng lặp (Question Deduplication).<br>• Quản lý trạng thái câu hỏi (`draft` $\rightarrow$ `accepted` / `rejected`). | `backend/exam_builder.py`<br>`backend/schemas.py`<br>`tests/test_generation_quality.py` |

---

## 4. KẾ HOẠCH VÀ LỘ TRÌNH TRIỂN KHAI CHI TIẾT 12 TUẦN

Lộ trình 12 tuần được xây dựng bám sát thực tế phát triển một đề tài kỹ thuật phần mềm ứng dụng AI, có tính khả thi cao và nằm trọn vẹn trong tầm kiểm soát của nhóm sinh viên:

```text
Giai đoạn 1: Khởi động & Chuẩn hóa Kiến trúc (Tuần 1 - 3) [ĐÃ HOÀN THÀNH ✅]
    │
    ▼
Giai đoạn 2: Xây dựng RAG Pipeline & Xử lý Dữ liệu - M2 (Tuần 4 - 5) [CẢ 3 LÀM]
    │
    ▼
Giai đoạn 3: Hệ thống Sinh Câu hỏi bằng AI & Kiểm soát - M3 (Tuần 6 - 7) [CẢ 3 LÀM]
    │
    ▼
Giai đoạn 4: Thiết kế Giao diện Người dùng Next.js - M4.A (Tuần 8)
    │
    ▼
Giai đoạn 5: Tích hợp Hệ thống End-to-End & Review Flow - M4.B (Tuần 9)
    │
    ▼
Giai đoạn 6: Tối ưu hóa, Tinh chỉnh Prompt & Đánh giá Hiệu năng (Tuần 10)
    │
    ▼
Giai đoạn 7: Kiểm thử Toàn diện & Thử nghiệm Thực tế (Tuần 11)
    │
    ▼
Giai đoạn 8: Đóng gói Sản phẩm, Viết Báo cáo & Chuẩn bị Bảo vệ - M5 (Tuần 12)
```

### Bảng kế hoạch chi tiết từng tuần:

| Tuần | Mục tiêu giai đoạn | Sinh viên 1 (SV1) | Sinh viên 2 (SV2) | Sinh viên 3 (SV3) | Kết quả bàn giao (Deliverables) |
|:---:|---|---|---|---|---|
| **Tuần 1** | **M0: Khảo sát & Môi trường** | Khảo sát thư viện xử lý tài liệu Python (`pypdf`, `python-docx`), cài môi trường. | Tìm hiểu API Google Gemini, LangChain và vector DB ChromaDB. | Thiết lập repository chung, cài đặt Node.js/FastAPI, chạy thử nghiệm baseline QuestGen. | Repo nhóm hoạt động, hướng dẫn cài đặt môi trường. |
| **Tuần 2** | **M1: Thiết kế Kiến trúc & Schemas** | Thiết kế cấu trúc dữ liệu tài liệu (`Document`, `ChunkMetadata`). | Thiết kế cấu trúc câu hỏi trắc nghiệm chuẩn (`QuestionSchema`, `Option`). | Biên soạn đặc tả hợp đồng `docs/API_CONTRACT.md`, viết `backend/schemas.py`. | Tài liệu API contract và mô hình dữ liệu Pydantic v2. |
| **Tuần 3** | **M1: Chuẩn bị Test & Dữ liệu mẫu** | Tạo bộ file tài liệu kiểm thử mẫu (`.pdf`, `.docx`, `.txt`, file rỗng, file lỗi). | Định nghĩa dữ liệu bàn giao mẫu giữa các module (`sample_m2_handoff.json`). | Viết và chạy 100% pass bộ unit test hợp đồng (`test_contract.py`, `test_m2_contracts.py`). | 6/6 test contract passed, bộ fixtures mẫu đầy đủ. |
| **Tuần 4** | **M2: Khởi tạo RAG Pipeline (Cả 3 làm)** | **Lập trình bộ bóc tách text PDF/Word/TXT trong `backend/documents.py`.** | **Nghiên cứu & code thuật toán cắt đoạn (Chunking) có window overlap.** | **Khởi tạo ChromaDB collection theo từng `course_id`, tạo hàm retrieval cơ sở.** | Parser đọc được text từ 3 định dạng file mẫu. |
| **Tuần 5** | **M2: Hoàn thiện RAG & Trích dẫn (Cả 3 làm)** | **Bắt lỗi file rỗng, tính hash SHA-256 chống trùng, viết `test_documents.py`.** | **Nhúng vector (Embedding) và lưu vào ChromaDB, viết `test_ingestion.py`.** | **Lọc tìm kiếm ngữ nghĩa theo môn học, đóng gói trích dẫn `source_refs`.** | Hoàn thành toàn diện M2, 100% unit tests M2 pass. |
| **Tuần 6** | **M3: Khởi tạo Sinh AI (Cả 3 làm)** | **Thiết kế System/User Prompt, ép LLM bám sát bài học (Grounding).** | **Tích hợp Gemini API qua SDK Async, quản lý token và tham số mô hình.** | **Xây dựng bộ phân tích cú pháp JSON từ LLM, bắt lỗi định dạng đầu ra.** | Module gọi được Gemini API và nhận về danh sách câu hỏi dạng thô. |
| **Tuần 7** | **M3: Kiểm định Chất lượng (Cả 3 làm)** | **Prompt sinh giải thích chi tiết đáp án và ánh xạ nguồn trích dẫn.** | **Cài đặt cơ chế chịu lỗi Retry / Exponential Backoff khi API gặp sự cố.** | **Lập trình Quality Gatekeeper: kiểm tra 4 phương án, lọc câu trùng, test M3.** | Pipeline M3 hoàn chỉnh, câu hỏi sinh ra chuẩn schema, không bị lỗi cú pháp. |
| **Tuần 8** | **M4.A: Phát triển Giao diện (UI)** | Phối hợp làm UI Upload tài liệu và thanh tiến trình xử lý file. | Phối hợp làm UI cài đặt sinh câu hỏi (chọn chủ đề, số lượng câu, độ khó). | Chủ trì thiết kế giao diện Next.js, xây dựng layout trang học tập và thẻ câu hỏi. | Bộ giao diện Next.js tương tác trực quan chạy tại `localhost:3000`. |
| **Tuần 9** | **M4.B: Tích hợp E2E & Review Flow** | Đấu nối API tài liệu với giao diện người dùng, hiển thị danh sách tài liệu. | Đấu nối API sinh câu hỏi với giao diện, xử lý trạng thái loading/timeout. | Lập trình chức năng Duyệt câu hỏi (Review Flow: Nút Chấp nhận / Loại bỏ), nối toàn luồng. | Luồng End-to-End hoàn chỉnh: Upload $\rightarrow$ RAG $\rightarrow$ AI Sinh $\rightarrow$ Duyệt câu hỏi. |
| **Tuần 10** | **Tối ưu hóa & Đánh giá (Eval)** | Tối ưu tốc độ bóc tách văn bản đối với file PDF dung lượng lớn (>15 trang). | Tinh chỉnh prompt và đánh giá chất lượng câu hỏi (tỷ lệ câu đúng/sai, độ khó). | Tối ưu giao diện, thêm thông báo trạng thái (Toast notify), cache dữ liệu câu hỏi. | Báo cáo đánh giá chất lượng câu hỏi thực tế trên 3 bộ tài liệu môn học. |
| **Tuần 11** | **M5.A: Kiểm thử Tổng thể & Thử nghiệm** | Tạo thêm các ca kiểm thử biên (file tiếng Việt có dấu, file nhiều bảng biểu). | Đo lường độ trễ (latency), kiểm tra tính ổn định khi gọi API liên tục. | Tổ chức thử nghiệm người dùng thử (User Acceptance Test), sửa lỗi (bug fix). | Biên bản thử nghiệm người dùng, hệ thống ổn định không phát sinh lỗi nghiêm trọng. |
| **Tuần 12** | **M5.B: Đóng gói, Báo cáo & Bảo vệ** | Viết phần báo cáo đồ án: Khảo sát, Xử lý dữ liệu và Kiến trúc RAG. | Viết phần báo cáo đồ án: Mô hình LLM, Prompt Engineering và Đánh giá. | Tổng hợp báo cáo tổng kết, hoàn thiện README, làm slide và video demo. | Báo cáo đồ án hoàn chỉnh, Slide thuyết trình và Video demo bảo vệ đề tài. |

---

## 5. PHÂN BỔ NHIỆM VỤ TỔNG THỂ CHO TỪNG THÀNH VIÊN

### 👨‍💻 Sinh viên 1 (SV1): Kỹ sư Dữ liệu & Ngữ cảnh Prompt
- **Trách nhiệm chính:**
  1. Phụ trách toàn bộ khâu tiếp nhận, xác thực và bóc tách dữ liệu bài giảng đa định dạng (.pdf, .docx, .txt) kèm số trang chính xác (Tuần 4 - 5).
  2. Phụ trách tầng ngữ cảnh AI: Ghép nối Context từ RAG và kỹ thuật Prompt Engineering chuyên sâu chống bịa đặt kiến thức (Tuần 6 - 7).
  3. Xây dựng bộ dữ liệu kiểm thử mẫu và viết báo cáo chuyên đề về RAG & Data Extraction (Tuần 3, 10, 12).

### 👨‍💻 Sinh viên 2 (SV2): Kỹ sư AI & Hệ thống Vector DB
- **Trách nhiệm chính:**
  1. Xây dựng thuật toán phân chia văn bản (Chunking) và nạp chỉ mục vào ChromaDB kèm metadata (Tuần 4 - 5).
  2. Tích hợp mô hình ngôn ngữ lớn (Google Gemini API / OpenAI / Ollama), xây dựng cơ chế chịu lỗi Async Retry / Backoff (Tuần 6 - 7).
  3. Đo lường hiệu năng, tinh chỉnh tham số mô hình và thực hiện đánh giá chất lượng câu hỏi sinh ra (Tuần 10, 11, 12).

### 👨‍💻 Sinh viên 3 (SV3): Kỹ sư Giao diện, Tích hợp & Trưởng nhóm
- **Trách nhiệm chính:**
  1. Lập trình module tìm kiếm ngữ nghĩa theo môn học (`course_id`) và đóng gói nguồn trích dẫn (`source_refs`) (Tuần 4 - 5).
  2. Xây dựng bộ lọc kiểm định chất lượng (Quality Gatekeeper) và thuật toán lọc câu hỏi trùng lặp (Tuần 6 - 7).
  3. Chủ trì phát triển giao diện Next.js, xây dựng tính năng Duyệt câu hỏi (Review Flow) và tích hợp liên thông toàn bộ hệ thống (Tuần 8 - 9).
  4. Quản lý tiến độ chung của nhóm trên GitHub, điều phối kiểm thử E2E, chuẩn bị slide và video demo báo cáo (Tuần 1 - 3, 11, 12).

---

## 6. QUY CHUẨN LÀM VIỆC NHÓM VÀ BẢO ĐẢM TIẾN ĐỘ

1. **Quản lý phiên bản trên Git:**
   - Nhánh `main` là nhánh ổn định, chỉ merge code khi đã kiểm thử thành công.
   - Nhánh tính năng được đặt tên theo tuần và nhiệm vụ, ví dụ:
     - `feature/w04-sv1-pdf-parser`
     - `feature/w04-sv2-chunking`
     - `feature/w05-sv3-retrieval`
     - `feature/w06-sv2-gemini-async`
     - `feature/w08-sv3-ui-layout`
   - Bắt buộc phải tạo Pull Request (PR) và có ít nhất 1 thành viên review trước khi merge.
2. **Tiêu chuẩn nghiệm thu (Definition of Done - DoD):**
   - Viết Unit test cho từng hàm xử lý; tỷ lệ pass đạt 100%.
   - Xử lý triệt để các lỗi ngoại lệ (file rỗng, mất mạng, token vượt ngưỡng, LLM trả dữ liệu sai format).
   - Bảo mật tuyệt đối: Không đưa API key hay file cấu hình môi trường `.env` lên GitHub.

---

## 7. BÁO CÁO TIẾN ĐỘ THỰC TẾ (TÍNH ĐẾN THỜI ĐIỂM HIỆN TẠI)

> 📍 **Hiện trạng thực tế của nhóm:** Nhóm đã hoàn thành xong **Tuần 1, Tuần 2 và Tuần 3 (Giai đoạn M0 & M1)**, hiện đang sẵn sàng bước vào **Tuần 4 (Triển khai giai đoạn M2)**.

- **Minh chứng các kết quả đã hoàn thành:**
  - [x] Khảo sát thành công mã nguồn QuestGen, chạy thử nghiệm baseline an toàn.
  - [x] Biên bản chốt phạm vi MVP rõ ràng (`docs/meeting-notes/decisions.md`).
  - [x] Tài liệu kiến trúc hệ thống tổng quan (`docs/ARCHITECTURE.md`).
  - [x] Hợp đồng API chuẩn mực giữa Frontend và Backend (`docs/API_CONTRACT.md`).
  - [x] Định nghĩa toàn bộ cấu trúc dữ liệu bằng Pydantic v2 trong `backend/schemas.py`.
  - [x] Bộ tài liệu mẫu đầy đủ trong `tests/fixtures/` (`sample_lecture.pdf`, `sample_lecture.docx`, `sample_course_doc.txt`, `empty_file.txt`, `invalid_file.xyz`).
  - [x] Vượt qua 100% bài kiểm thử hợp đồng dữ liệu trong `tests/test_contract.py` và `tests/test_m2_contracts.py`.

- **Kế hoạch triển khai ngay trong Tuần 4:**
  - **SV1:** Bắt đầu lập trình parser đọc file PDF, Word, TXT trong `backend/documents.py`.
  - **SV2:** Viết bộ chia đoạn (Chunking) trong `backend/ingestion.py`.
  - **SV3:** Thiết lập ChromaDB và viết khung hàm truy xuất môn học trong `backend/retrieval.py`.

---

*Hà Nội, ngày 23 tháng 10 năm 2026*  
**Đại diện nhóm sinh viên thực hiện**  
*(Ký và ghi rõ họ tên)*
