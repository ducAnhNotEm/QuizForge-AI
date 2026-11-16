# IMPLEMENTATION_PLAN.md
# AI Tutor – Kế hoạch triển khai nhóm 3 người

> **Repo tham khảo:** https://github.com/cRED-f/QuestGen-AI-Agent  
> **Mục tiêu:** Xây dựng phiên bản AI Tutor dành cho sinh viên, tái sử dụng có chọn lọc nền tảng QuestGen và phát triển theo từng milestone có thể kiểm thử.  
> **Trạng thái:** Kế hoạch đề xuất — chưa phải bằng chứng rằng các task đã hoàn thành.

---

## 1. Phạm vi sản phẩm (MVP)

Người dùng có thể:
1. Tạo một không gian học tập cho một môn học/chủ đề.
2. Tải tài liệu PDF, DOCX hoặc TXT.
3. Hệ thống trích xuất nội dung và lập chỉ mục để truy xuất.
4. Người dùng yêu cầu sinh câu hỏi trắc nghiệm từ tài liệu đã tải lên.
5. Mỗi câu hỏi có 4 lựa chọn, một đáp án dự kiến đúng, giải thích ngắn và nguồn tham chiếu nếu pipeline hiện tại hỗ trợ.
6. Người dùng xem lại, chỉnh sửa, chấp nhận hoặc loại câu hỏi.
7. Chạy kiểm thử và trình diễn luồng end-to-end.
8. Học sinh làm bài trắc nghiệm, hệ thống chấm điểm và hiển thị giải thích kèm nguồn sau khi nộp.
9. Hệ thống ước lượng mức nắm vững (Mastery) theo từng khái niệm và hiển thị trực quan cho học sinh.
10. Hệ thống đề xuất hoặc tự động sinh câu hỏi tiếp theo thích ứng theo trình độ của học sinh.

**Không làm trong MVP:** tài khoản/đăng nhập phức tạp (dùng `learner_id` ẩn danh theo phiên), triển khai production, thanh toán, hỗ trợ mọi định dạng file, tự động khẳng định câu hỏi đúng tuyệt đối. Ưu tiên dùng chức năng sẵn có thay vì viết lại toàn bộ.

## 2. Quy tắc trước khi bắt đầu

- Không push trực tiếp vào repo upstream `cRED-f/QuestGen-AI-Agent`. Tạo fork hoặc repo riêng thuộc nhóm.
- Repo tham khảo có giấy phép MIT; giữ lại `LICENSE` và thông báo bản quyền cần thiết khi tái sử dụng mã. Kiểm tra các thư viện/tài sản riêng lẻ nếu có giấy phép khác.
- Không commit `.env`, API key, dữ liệu cá nhân hoặc tài liệu học có bản quyền nếu chưa được phép.
- Trước khi sửa một module lớn, chạy ứng dụng gốc và ghi lại trạng thái baseline.
- Mỗi PR phải có mô tả, cách kiểm thử, ảnh/video nếu thay đổi UI; không merge PR đỏ hoặc không chạy được.
- Không tuyên bố một task hoàn thành nếu chưa có bằng chứng chạy/test.

## 3. Phân công 3 thành viên

| Thành viên | Vai trò chính | Khu vực phụ trách | Kết quả bàn giao |
|---|---|---|---|
| **SV1** | Tài liệu, RAG & Dữ liệu Khái niệm | `backend/documents.py`, `backend/ingestion.py`, `backend/concepts.py`, `backend/learner_store.py`, `backend/routes_learning_data.py` | Upload → trích xuất → chunk/index → trích xuất khái niệm & quản lý trạng thái học sinh (E1–E5) |
| **SV2** | Sinh câu hỏi & Thuật toán Thích ứng | `backend/generation.py`, `backend/mastery.py`, `backend/selection.py`, `backend/adaptive_config.py`, `backend/routes_adaptive.py` | Sinh câu hỏi theo schema v2, ước lượng mastery, chọn câu theo ZPD, nộp bài & chẩn đoán (E6–E9) |
| **SV3** | UI Next.js, Tích hợp, Mô phỏng & QA | `app/`, `backend/retrieval.py`, `scripts/simulate_learners.py`, UI components, điều phối API và E2E | Luồng người dùng hoàn chỉnh (giáo viên + học sinh), đăng ký router, mô phỏng thích ứng, đánh giá |

**Lưu ý:** Đây là phân công sở hữu chính, không có nghĩa chỉ một người được đọc các file đó. `backend/app.py` là file lớn và có thể chứa nhiều route; không để cả 3 người sửa cùng lúc. SV3 điều phối API/integration, người sửa route cần tạo PR nhỏ và thông báo trước.

## 4. Milestones và task checklist

### M0 — Khảo sát, thiết lập và baseline
**Phụ trách:** Cả nhóm; SV3 điều phối.

- [ ] M0.1 — Tạo fork hoặc repo riêng của nhóm, giữ license/credit của dự án gốc.
- [ ] M0.2 — Đọc README, `.env.example`, `backend/requirements.txt`, `package.json`.
- [ ] M0.3 — Cài môi trường Node.js 20.9+, Python 3.11+ và dependencies.
- [ ] M0.4 — Chạy backend bằng `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload`.
- [ ] M0.5 — Chạy frontend bằng `npm install` rồi `npm run dev`.
- [ ] M0.6 — Kiểm tra `/api/health`, mở `/chat`, cấu hình provider/model và thử một yêu cầu đơn giản.
- [ ] M0.7 — Chạy baseline tests: `PYTHONPATH=. pytest backend/tests -q`; ghi rõ test nào pass/fail và lỗi môi trường nếu có.
- [ ] M0.8 — Chốt phạm vi MVP và ghi lại chức năng gốc sẽ giữ, ẩn hoặc thay đổi.

**Điều kiện hoàn thành:** ít nhất một thành viên chạy được ứng dụng; cả nhóm có hướng dẫn setup tái lập; lỗi baseline được ghi nhận, không bị nhầm là lỗi do nhóm tạo ra.

### M1 — Thiết kế hợp đồng giữa các module
**Phụ trách:** SV1 + SV2; SV3 ghi vào tài liệu.

- [x] M1.1 — Chốt luồng: chọn môn/tài liệu → upload/index → yêu cầu sinh câu hỏi → xem nguồn → review câu hỏi.
- [x] M1.2 — Chốt schema câu hỏi và response API trước khi code song song.
- [x] M1.3 — Chốt cách thể hiện lỗi: file không hỗ trợ, tài liệu rỗng, chưa cấu hình model, model timeout, đầu ra sai schema.
- [x] M1.4 — Thêm `docs/API_CONTRACT.md` mô tả endpoint thực tế sau khi đối chiếu `backend/app.py`; không tự đặt endpoint rồi coi là đã tồn tại.
- [x] M1.5 — Tạo fixture tài liệu nhỏ, không chứa thông tin nhạy cảm, dùng chung cho test.

**Schema đề xuất cho một câu hỏi:**
```json
{
  "id": "string",
  "type": "mcq",
  "question": "string",
  "options": [
    {"id": "A", "text": "string"},
    {"id": "B", "text": "string"},
    {"id": "C", "text": "string"},
    {"id": "D", "text": "string"}
  ],
  "correct_option_id": "A",
  "explanation": "string",
  "source_refs": [],
  "status": "draft"
}
```
Schema trên là **hợp đồng mục tiêu ban đầu**; cần ánh xạ sang cấu trúc hiện có trước khi sửa để tránh phá vỡ tương thích.
> 💡 *Lưu ý:* Ở Milestone M3A, schema này được mở rộng tương thích ngược sang **Schema v2** (bổ sung `concept_id`, `difficulty` logit $b$, `bloom_level`, `distractor_rationales`).

**Điều kiện hoàn thành:** SV1, SV2, SV3 cùng duyệt hợp đồng; có ít nhất một test/fixture minh họa dữ liệu đầu vào và đầu ra.

### M2 — Tài liệu và retrieval (Phối hợp 3 thành viên: SV1 + SV2 + SV3)
**Điều phối:** SV1 (Input & Parser) + SV2 (Chunking & Indexing) + SV3 (Retrieval & Citation).

- **SV1 (Input & File Parsing)**:
  - [x] M2.1 — Viết bộ bóc tách văn bản đa định dạng (.pdf, .docx, .txt) trong `backend/documents.py`.
  - [x] M2.2 — Bắt lỗi file rỗng, lỗi định dạng, và chặn file trùng lặp qua checksum SHA-256 (kèm chuẩn hóa NFC tiếng Việt).
  - [x] M2.3 — Viết unit test `tests/test_documents.py` kiểm thử các ca đọc file thành công và thất bại.

- **SV2 (Chunking & Vector Storage)**:
  - [x] M2.4 — Xây dựng bộ chia đoạn văn bản (Text Chunker) có window overlap trong `backend/ingestion.py`.
  - [x] M2.5 — Lưu trữ chunk vào Vector DB / CSDL kèm metadata phân vùng môn học (`course_id`, `page`, `doc_id`) và băm ID an toàn.
  - [x] M2.6 — Viết unit test `tests/test_ingestion.py` kiểm thử độ dài chunk và tính toàn vẹn metadata.

- **SV3 (Course-Scoped Retrieval & Citation)**:
  - [x] M2.7 — Xây dựng hàm tìm kiếm ngữ nghĩa theo môn học trong `backend/retrieval.py` đảm bảo cách ly tuyệt đối (`course_id`).
  - [x] M2.8 — Đóng gói danh sách trích dẫn nguồn (`source_refs`) chuẩn theo Hợp đồng API (kèm `page`, `snippet`).
  - [x] M2.9 — Viết unit test `tests/test_retrieval.py` kiểm thử độ chính xác truy xuất và bàn giao cho M3.

**Tài liệu mẫu fixture có sẵn để kiểm thử (`tests/fixtures/`):**
- `sample_lecture.pdf`: File PDF 2 trang thực tế để test trích xuất số trang.
- `sample_lecture.docx`: File Word có tiêu đề và đoạn văn để test đọc DOCX.
- `sample_course_doc.txt`: File văn bản bài học để test đọc TXT.
- `empty_file.txt`: File 0 bytes để test bắt lỗi file rỗng.
- `invalid_file.xyz`: File sai định dạng để test bắt lỗi file không hỗ trợ.
- `sample_m2_handoff.json`: Dữ liệu mẫu bàn giao giữa SV1 $\rightarrow$ SV2 $\rightarrow$ SV3.

**Điều kiện hoàn thành:** Cả 3 module vượt qua 100% unit tests của từng thành viên với các fixture mẫu đã có.

### M3 — Sinh câu hỏi bằng AI & Đảm bảo Chất lượng (Phối hợp 3 thành viên: SV1 + SV2 + SV3)
**Điều phối:** SV1 (Prompt & Context) + SV2 (LLM Integration & Resilience) + SV3 (Quality Gatekeeper & Deduplication).

- **SV1 (Context Injection & Prompt Engineering)**:
  - [ ] M3.1 — Tiếp nhận kết quả từ retrieval, làm sạch và đóng gói vào cấu trúc Context đưa vào LLM (`backend/exam_context.py`).
  - [ ] M3.2 — Thiết kế kỹ thuật Prompt Engineering chuyên sâu (System prompt + User prompt) buộc mô hình bám sát tài liệu bài giảng (Grounding), chống bịa đặt kiến thức (Hallucination) (`backend/prompts.py`).
  - [ ] M3.3 — Yêu cầu mô hình sinh giải thích chi tiết vì sao đáp án đúng và vì sao 3 phương án còn lại sai (kèm trích dẫn nguồn).
  - [ ] M3.4 — Viết unit test `tests/test_prompt_context.py` kiểm thử khả năng đóng gói context và chất lượng prompt.

- **SV2 (LLM Integration & Resilience Pipeline)**:
  - [ ] M3.5 — Tích hợp các LLM Provider: Google Gemini API (SDK Async), OpenAI GPT và Local LLM Ollama (`backend/generation.py`, `backend/llm_client.py`).
  - [ ] M3.6 — Xây dựng cơ chế gọi API bất đồng bộ (Async), quản lý token limit và tối ưu tham số mô hình (`temperature`, `top_p`).
  - [ ] M3.7 — Xử lý chống nghẽn và chịu lỗi: Cơ chế Retry với Exponential Backoff khi API mạng bị ngắt quãng hoặc gặp rate-limit.
  - [ ] M3.8 — Viết unit test `tests/test_llm_resilience.py` kiểm thử cơ chế gọi API và tự động thử lại khi timeout.

- **SV3 (Quality Gatekeeper & Deduplication)**:
  - [ ] M3.9 — Xây dựng bộ lọc kiểm định chất lượng đầu ra: Validate nghiêm ngặt JSON Schema bằng Pydantic v2 (chặn lỗi JSON méo, thiếu trường, sai kiểu dữ liệu).
  - [ ] M3.10 — Kiểm tra logic đề thi: Đúng 4 phương án độc lập (A, B, C, D), không có lựa chọn trùng nhau, đáp án đúng phải thuộc danh sách lựa chọn (`backend/mcq_parsing.py`, `backend/schemas.py`).
  - [ ] M3.11 — Lập trình thuật toán phát hiện và lọc câu hỏi trùng lặp (Question Deduplication).
  - [ ] M3.12 — Quản lý trạng thái câu hỏi (`draft` → `accepted` / `rejected`), lưu trữ câu hỏi nháp an toàn.
  - [ ] M3.13 — Viết unit test `tests/test_generation_quality.py` kiểm thử tính toàn vẹn câu hỏi và loại bỏ câu trùng lặp.

**Điều kiện hoàn thành:** Với context mẫu từ M2, pipeline M3 gọi được LLM, tự động bắt lỗi/retry khi mạng chập chờn, trả về danh sách câu hỏi chuẩn schema Pydantic, lọc sạch câu hỏi trùng và vượt qua 100% unit tests của cả 3 thành viên.

### M3A — Học thích ứng: ước lượng mức nắm vững và chọn câu hỏi theo trình độ
**Phụ trách:** Cả nhóm. SV1 (khái niệm + dữ liệu), SV2 (mastery + chọn câu + sinh câu có tham số), SV3 (hợp đồng API, tích hợp, mô phỏng, đánh giá).
**Phụ thuộc:** M1 (hợp đồng), M2 (chunk có metadata), M3 (pipeline sinh câu). Hoàn thành trước khi làm phần UI thích ứng của M4.

**Mục tiêu:** học sinh làm bài → hệ thống ghi nhận câu trả lời → ước lượng mức nắm vững theo từng khái niệm → chọn hoặc sinh câu hỏi tiếp theo phù hợp trình độ.

**Không làm trong M3A:** đăng nhập/tài khoản thật (dùng `learner_id` ẩn danh), IRT/BKT đầy đủ, học sâu, khẳng định hiệu quả sư phạm khi chưa có dữ liệu thí điểm.

#### Nguyên tắc thiết kế
- `learner_id` ẩn danh, không lưu thông tin cá nhân.
- **Không gửi `correct_option_id` và `explanation` cho client trước khi học sinh nộp câu trả lời.** Chỉ trả sau `POST /api/attempts`.
- Mặc định chỉ phục vụ câu có `status = accepted`. Cờ cấu hình `SERVE_UNREVIEWED_QUESTIONS` (mặc định `false`) cho phép phục vụ câu `draft` trong chế độ demo; UI phải hiển thị nhãn "chưa được duyệt".
- Mọi tham số số học nằm trong một file duy nhất `backend/adaptive_config.py`. Các giá trị bên dưới là **giá trị khởi điểm**, cần hiệu chỉnh bằng mô phỏng và dữ liệu thật.
- Test không gọi model thật; mock LLM bằng fixture.
- Endpoint dưới đây là **đề xuất**. Phải đối chiếu với `backend/app.py` và ghi vào `docs/API_CONTRACT.md` trước khi code (xem M3A.14).

#### Mô hình dữ liệu đề xuất
Dùng CSDL hiện có của dự án (chốt ở M0). Tên bảng/cột có thể đổi theo cấu trúc thực tế.

| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `concepts` | `concept_id`, `course_id`, `name`, `description`, `importance` | `importance` mặc định 1.0 |
| `chunk_concepts` | `chunk_id`, `concept_id` | Một chunk gắn 1-2 khái niệm |
| `learners` | `learner_id`, `created_at` | Ẩn danh |
| `attempts` | `attempt_id`, `client_attempt_id` (unique), `learner_id`, `course_id`, `question_id`, `concept_id`, `chosen_option_id`, `is_correct`, `time_spent_ms`, `session_id`, `weight`, `theta_before`, `theta_after`, `created_at` | `client_attempt_id` dùng để chống ghi trùng |
| `learner_concept_state` | `learner_id`, `concept_id`, `theta`, `n_attempts`, `n_correct`, `last_seen_at` | Khóa chính (`learner_id`, `concept_id`) |
| `question_stats` | `question_id`, `b`, `n_attempts`, `n_correct`, `b_source` | `b_source`: `llm` hoặc `calibrated` |

#### Schema câu hỏi v2 (mở rộng tương thích ngược)
Thêm các trường sau vào schema ở M1. Câu cũ thiếu các trường này vẫn hợp lệ nhưng **không** được đưa vào luồng thích ứng.

```json
{
  "schema_version": 2,
  "concept_id": "string",
  "difficulty": { "label": "easy|medium|hard", "b": 0.0, "source": "llm|calibrated" },
  "bloom_level": "remember|understand|apply|analyze",
  "distractor_rationales": {
    "B": "Học sinh chọn đáp án này khi nhầm ... ",
    "C": "string",
    "D": "string"
  }
}
```
Quy tắc kiểm tra thêm (bổ sung cho M3.4): `concept_id` tồn tại trong course; `distractor_rationales` có đủ 3 khóa cho 3 lựa chọn sai; `bloom_level` và `difficulty.label` thuộc tập cho phép. Độ khó ban đầu: `easy → b = -1.0`, `medium → 0.0`, `hard → +1.0`.

#### Logic ước lượng mức nắm vững (mastery)
Mỗi cặp (học sinh, khái niệm) có một năng lực `theta` (thang logit, khởi tạo 0). Mỗi câu hỏi có độ khó `b`. Dùng mô hình kiểu Elo có sàn đoán mò cho câu 4 lựa chọn.

```python
import math

G = 0.25                      # sàn đoán mò (4 lựa chọn)
K0, K_MIN = 0.5, 0.1          # tốc độ học của theta, giảm dần theo số lần làm
KB0, KB_MIN = 0.2, 0.02       # tốc độ hiệu chỉnh độ khó câu hỏi
TAU_DAYS = 14.0               # hằng số quên
THETA_RANGE = (-4.0, 4.0)
B_RANGE = (-3.0, 3.0)

def clamp(x, lo, hi): return max(lo, min(hi, x))
def sigmoid(x): return 1 / (1 + math.exp(-x))

def p_correct(theta, b):
    return G + (1 - G) * sigmoid(theta - b)

def effective_theta(theta, last_seen_at, now):
    """Quên dần: theta co về 0 (mức chưa biết) khi lâu không ôn."""
    days = max(0.0, (now - last_seen_at).total_seconds() / 86400)
    return theta * math.exp(-days / TAU_DAYS)

def update(theta_eff, b, n_concept, n_item, is_correct, weight=1.0):
    p = p_correct(theta_eff, b)
    err = (1.0 if is_correct else 0.0) - p
    k_theta = max(K_MIN, K0 / (1 + n_concept / 5))
    k_b = max(KB_MIN, KB0 / (1 + n_item / 10))
    new_theta = clamp(theta_eff + weight * k_theta * err, *THETA_RANGE)
    new_b = clamp(b - weight * k_b * err, *B_RANGE)
    return new_theta, new_b, p

def mastery(theta_eff):
    return sigmoid(theta_eff)
```

**Trọng số `weight`:** mặc định 1.0. Trả lời sai trong thời gian rất ngắn (`time_spent_ms < 3000`) coi là bấm bừa, đặt `weight = 0.5`. Ngưỡng nằm trong config.

**Trạng thái hiển thị:**

| Điều kiện | Trạng thái |
|---|---|
| `n_attempts < 3` | `unknown` (chưa đủ dữ liệu) |
| `mastery < 0.4` | `weak` |
| `0.4 ≤ mastery < 0.7` | `learning` |
| `mastery ≥ 0.7` | `mastered` |

**Ví dụ kiểm chứng (dùng làm test):** `theta = 0`, `b = 0`, `n_concept = 0`, `n_item = 0` → `p_correct = 0.625`. Trả lời đúng: `theta = 0.1875`. Trả lời sai: `theta = -0.3125`.

**Hiệu chỉnh độ khó:** `b` ban đầu lấy từ nhãn của LLM (kém tin cậy). Sau mỗi lượt làm, `b` được cập nhật theo công thức trên. Chỉ chuyển `b_source` sang `calibrated` khi câu có ít nhất 20 lượt làm từ ít nhất 5 học sinh khác nhau.

#### Chính sách chọn câu hỏi tiếp theo
1. **Chọn khái niệm:** với mỗi khái niệm `c` tính `score_c = importance_c * (1 - mastery_eff_c) + 0.3 / sqrt(1 + n_c)`. Lấy `score` cao nhất. Khái niệm lâu không ôn sẽ có `mastery_eff` về gần 0.5 nên tự được ưu tiên ôn lại.
2. **Xen kẽ:** không chọn cùng một khái niệm quá 2 câu liên tiếp trong một phiên.
3. **Độ khó mục tiêu:** nhắm xác suất đúng khoảng 70%: `b* = theta_eff - logit((0.70 - G) / (1 - G))`, tức `b* ≈ theta_eff - 0.405`. Quy đổi nhãn: `b* < -0.5` → easy, `-0.5 ≤ b* ≤ 0.5` → medium, `b* > 0.5` → hard.
4. **Mức Bloom:** `mastery_eff < 0.4` → remember/understand; `0.4-0.7` → apply; `≥ 0.7` → analyze.
5. **Chọn câu:** trong ngân hàng câu của khái niệm đó, loại câu học sinh đã làm, lấy câu có `|b - b*|` nhỏ nhất. Nếu nhỏ nhất vẫn lớn hơn 0.6, hoặc không còn câu nào, gọi sinh câu mới với tham số (khái niệm, nhãn độ khó, mức Bloom) rồi chạy lại quy trình kiểm tra của M3.
6. **Học sinh mới (cold start):** làm bài chẩn đoán 6-8 câu độ khó medium, phủ các khái niệm có `importance` cao nhất. Trong lượt đầu mỗi khái niệm, `theta` cập nhật nhanh hơn nhờ `K` còn lớn.

#### API endpoints (đề xuất, chưa phải endpoint đã tồn tại)

| # | Method | Path | Mục đích | Owner |
|---|---|---|---|---|
| E1 | `GET` | `/api/courses/{course_id}/concepts` | Danh sách khái niệm của môn | SV1 |
| E2 | `POST` | `/api/courses/{course_id}/concepts/extract` | Chạy trích xuất khái niệm từ các chunk | SV1 |
| E3 | `POST` | `/api/learners` | Tạo `learner_id` ẩn danh | SV1 |
| E4 | `GET` | `/api/learners/{learner_id}/courses/{course_id}/mastery` | Mức nắm vững theo khái niệm | SV1 |
| E5 | `POST` | `/api/learners/{learner_id}/courses/{course_id}/reset` | Xóa trạng thái học (dùng khi demo/test) | SV1 |
| E6 | `POST` | `/api/learners/{learner_id}/courses/{course_id}/diagnostic` | Bắt đầu bài chẩn đoán | SV2 |
| E7 | `GET` | `/api/learners/{learner_id}/courses/{course_id}/next-question` | Lấy câu tiếp theo (không kèm đáp án) | SV2 |
| E8 | `POST` | `/api/attempts` | Nộp câu trả lời, nhận đúng/sai và cập nhật mastery | SV2 |
| E9 | mở rộng endpoint sinh câu hiện có | (xác định ở M3A.14) | Thêm tham số `concept_id`, `difficulty_label`, `bloom_level`, `count` | SV2 |

**Ví dụ `POST /api/attempts`:**
```json
// request
{
  "client_attempt_id": "uuid",
  "learner_id": "string",
  "course_id": "string",
  "question_id": "string",
  "chosen_option_id": "B",
  "time_spent_ms": 14200,
  "session_id": "string"
}

// response 200
{
  "is_correct": false,
  "correct_option_id": "C",
  "explanation": "string",
  "source_refs": [],
  "mastery_update": {
    "concept_id": "string",
    "mastery_before": 0.50,
    "mastery_after": 0.42,
    "status": "learning"
  }
}
```
Gửi lại cùng `client_attempt_id` trả đúng kết quả đã lưu và **không** cập nhật mastery lần hai.

**Ví dụ `GET .../next-question`:**
```json
{
  "question": {
    "id": "string",
    "question": "string",
    "options": [{"id": "A", "text": "string"}, {"id": "B", "text": "string"},
                {"id": "C", "text": "string"}, {"id": "D", "text": "string"}],
    "concept_id": "string",
    "difficulty_label": "medium",
    "bloom_level": "apply",
    "reviewed": true
  },
  "reason": "weak_concept"
}
```
`reason` ∈ `diagnostic`, `weak_concept`, `review_due`, `exploration`.

**Mã lỗi cần định nghĩa thêm (bổ sung cho M1.3):** `LEARNER_NOT_FOUND` (404), `QUESTION_NOT_FOUND` (404), `INVALID_OPTION` (422), `NO_CONCEPTS` (course chưa trích khái niệm), `NO_SERVABLE_QUESTIONS` (không có câu phù hợp và sinh mới thất bại), `GENERATION_FAILED`.

**Để tránh xung đột trong `backend/app.py`:** mỗi người viết router riêng (SV1: `backend/routes_learning_data.py`, SV2: `backend/routes_adaptive.py`). SV3 mở một PR nhỏ duy nhất để đăng ký router vào `app.py` (xem M3A.15). Cách đăng ký phụ thuộc framework thực tế, xác nhận ở M0.

#### Task checklist

**Chung**
- [ ] M3A.1 — Họp chốt thiết kế: bảng dữ liệu, schema câu hỏi v2, công thức mastery, chữ ký hàm giữa SV1 và SV2 (`mastery.effective_theta`, `mastery.update`, `learner_store.get_state`, `learner_store.save_attempt_and_state`). Ghi quyết định vào `docs/meeting-notes/decisions.md`.

**SV1 — Khái niệm và lớp dữ liệu**
- [ ] M3A.2 — Tạo migration/schema cho 6 bảng và `backend/learner_store.py`. Ghi attempt và cập nhật trạng thái trong **cùng một transaction**; đảm bảo `client_attempt_id` unique.
- [ ] M3A.3 — Viết `backend/concepts.py`: trích 5-15 khái niệm cho mỗi môn từ các chunk, gộp trùng, tính `importance` (ví dụ theo mức phủ trong tài liệu).
- [ ] M3A.4 — Gắn chunk với khái niệm (`chunk_concepts`) và thêm khả năng lọc truy xuất theo `concept_id` (phối hợp với người sở hữu `backend/retrieval.py` ở M2, qua PR nhỏ).
- [ ] M3A.5 — Viết router và endpoint E1-E5.
- [ ] M3A.6 — Viết `tests/test_learner_store.py`, `tests/test_concepts.py`: transaction rollback khi lỗi, trùng `client_attempt_id`, reset chỉ xóa dữ liệu của một học sinh, khái niệm trùng được gộp, course rỗng trả `NO_CONCEPTS`.

**SV2 — Mastery, chọn câu, sinh câu có tham số**
- [ ] M3A.7 — Mở rộng schema/validator sang v2 (thêm các trường và quy tắc ở trên); câu v1 vẫn đọc được nhưng bị loại khỏi luồng thích ứng.
- [ ] M3A.8 — Viết `backend/mastery.py` (hàm thuần, không đụng CSDL) và `backend/adaptive_config.py` theo công thức ở trên.
- [ ] M3A.9 — Viết `backend/selection.py`: tính `score` khái niệm, xen kẽ, `b*`, ánh xạ Bloom, chọn câu từ ngân hàng, quyết định khi nào cần sinh mới.
- [ ] M3A.10 — Mở rộng pipeline sinh câu (E9): nhận `concept_id`, độ khó, Bloom; chỉ dùng chunk của khái niệm đó làm context; yêu cầu model trả `distractor_rationales`; câu mới luôn ở trạng thái `draft`.
- [ ] M3A.11 — Viết router và endpoint E6-E8, bao gồm bộ dựng bài chẩn đoán và áp dụng `weight` cho trả lời quá nhanh.
- [ ] M3A.12 — Viết `tests/test_mastery.py`, `tests/test_selection.py`: khớp ví dụ kiểm chứng (0.1875 / -0.3125), `theta` và `b` bị chặn trong khoảng, `K` giảm theo số lần làm, quên dần làm `theta` co về 0, chọn khái niệm yếu trước, không lặp câu đã làm, không quá 2 câu liên tiếp cùng khái niệm, nộp trùng `client_attempt_id` không cập nhật lần hai.
- [ ] M3A.13 — *(Tùy chọn, làm nếu còn thời gian)* Khi học sinh hay chọn một đáp án sai, đưa `distractor_rationales` tương ứng vào prompt để sinh câu mới nhắm đúng hiểu lầm đó.

**SV3 — Hợp đồng, tích hợp, mô phỏng, đánh giá**
- [ ] M3A.14 — Cập nhật `docs/API_CONTRACT.md` sau khi đối chiếu `backend/app.py`: chốt đường dẫn thật cho E1-E9, schema v2, mã lỗi; ghi rõ endpoint nào là mới, endpoint nào là mở rộng.
- [ ] M3A.15 — PR nhỏ đăng ký hai router vào `backend/app.py`; chạy lại toàn bộ test baseline để xác nhận không phá endpoint cũ.
- [ ] M3A.16 — Viết `scripts/simulate_learners.py`: tạo học sinh giả có `theta` thật cho từng khái niệm, trả lời theo `p_correct`; kiểm tra `theta` ước lượng hội tụ về `theta` thật và chính sách chọn câu dồn vào khái niệm yếu. Ghi kết quả vào `docs/TEST_PLAN.md`. Dùng để hiệu chỉnh `K0`, `TAU_DAYS`, ngưỡng.
- [ ] M3A.17 — Viết `docs/EVALUATION_PLAN.md`: thí điểm với 3-5 người dùng thật, bài pre-test/post-test ngắn trên cùng tài liệu, cách ghi nhận kết quả. Với quy mô này chỉ báo cáo mô tả, **không** kết luận ý nghĩa thống kê.
- [ ] M3A.18 — Viết test tích hợp backend (mock LLM): tạo learner → chẩn đoán → nộp attempts → xem mastery → lấy câu tiếp theo; thêm các ca lỗi (learner không tồn tại, option sai, course chưa có khái niệm, sinh câu thất bại).

**Chung**
- [ ] M3A.19 — Ghi các giới hạn đã biết vào README/báo cáo (xem mục dưới).

**Fixture bổ sung trong `tests/fixtures/`:** `sample_concepts.json`, `sample_questions_v2.json`, `sample_attempts.json`.

**Thứ tự gợi ý:** M3A.1 → (M3A.2, M3A.7, M3A.8, M3A.14 chạy song song, không cần chờ M2/M3) → M3A.3, M3A.4 (cần chunk từ M2) → M3A.9, M3A.10 (cần pipeline M3 và concept từ SV1) → M3A.5, M3A.11 → M3A.15, M3A.16, M3A.18 → M3A.17, M3A.19.

#### Điều kiện hoàn thành M3A
- Toàn bộ test của M3A.6, M3A.12, M3A.18 pass; kết quả chạy được ghi trung thực trong PR.
- Mô phỏng (M3A.16) chạy lại được bằng một lệnh, kết quả lưu trong `docs/TEST_PLAN.md`.
- Một học sinh giả hoàn thành luồng chẩn đoán → làm bài → xem mastery → nhận câu tiếp theo qua API, và `next-question` không bao giờ lộ đáp án.
- Test baseline cũ vẫn chạy như trước khi thêm M3A.
- `docs/API_CONTRACT.md` khớp với endpoint thực tế.

#### Giới hạn đã biết (cần nêu trong báo cáo)
- Nhãn độ khó do LLM gán không đáng tin; `b` chỉ có ý nghĩa tương đối cho đến khi hiệu chỉnh bằng dữ liệu làm bài thật.
- Ước lượng từ vài câu rất nhiễu; trạng thái `unknown` tồn tại để tránh kết luận sớm.
- Mô hình chấm theo từng khái niệm và giả định các khái niệm độc lập; không mô hình hóa quan hệ tiên quyết giữa khái niệm.
- Chất lượng khái niệm phụ thuộc chất lượng trích xuất và tài liệu đầu vào.
- Mô phỏng chỉ chứng minh cài đặt đúng với giả định của mô hình, không chứng minh học sinh học tốt hơn. Hiệu quả sư phạm chỉ có thể nhận định sau thí điểm (M3A.17), và với mẫu nhỏ chỉ là mô tả.
- Các hằng số (`K0`, `TAU_DAYS`, ngưỡng 0.4/0.7, mục tiêu 70%) là lựa chọn khởi điểm, không phải giá trị đã được kiểm chứng.

---

## Cập nhật kèm theo ở các mục khác của IMPLEMENTATION_PLAN.md

**Mục 1 (Phạm vi MVP):** thêm các bước sau vào danh sách chức năng:
8. Học sinh làm bài, hệ thống chấm và hiển thị giải thích sau khi nộp.
9. Hệ thống ước lượng mức nắm vững theo từng khái niệm và hiển thị cho học sinh.
10. Hệ thống đề xuất hoặc sinh câu tiếp theo theo mức nắm vững.

Sửa dòng "Không làm" thành: không có tài khoản/đăng nhập, dùng `learner_id` ẩn danh theo phiên.

**Mục 3 (Phân công):** nếu nhóm đồng ý, để SV1 sở hữu toàn bộ M2 (SV2 hỗ trợ phần chunking) nhằm giảm tải cho SV3, vì SV3 còn gánh UI, tích hợp và M3A.14-M3A.18. Dù chọn cách nào, M3A.4 cần phối hợp với người sở hữu `retrieval.py`.

**M1:** ghi chú rằng schema v2 (M3A) là mở rộng tương thích ngược của schema hiện tại.

**M4:** thêm các task UI cho học sinh:
- [ ] M4.9 — Chế độ làm bài: ẩn đáp án và giải thích đến khi nộp.
- [ ] M4.10 — Màn hình bài chẩn đoán cho học sinh mới.
- [ ] M4.11 — Hiển thị phản hồi sau mỗi câu: đúng/sai, giải thích, nguồn, thay đổi mastery.
- [ ] M4.12 — Bảng mức nắm vững theo khái niệm (`unknown/weak/learning/mastered`) và nút làm lại (reset).
- [ ] M4.13 — Nhãn "chưa được duyệt" khi bật `SERVE_UNREVIEWED_QUESTIONS`.

**M5:** thêm task:
- [ ] M5.8 — Chạy lại mô phỏng và ghi kết quả thí điểm trung thực, kể cả kết quả không như kỳ vọng.

**Mục 5 (Thứ tự phụ thuộc):**
```text
M0 Baseline
   ↓
M1 API/schema contract
   ↓
M2 Document & retrieval ─────┐
                             ├── M3A Adaptive (mastery, selection) ── M4 End-to-end integration
M3 Question generation ──────┘
   ↓
M5 QA, README, demo, report
```

**Mục 8 (Issue khởi tạo):** thêm

| Issue | Tiêu đề | Owner | Phụ thuộc |
|---|---|---|---|
| #11 | Chốt thiết kế adaptive, schema v2 và chữ ký hàm | SV1 + SV2 + SV3 | #2 |
| #12 | Khái niệm, lớp dữ liệu learner/attempt và endpoint E1-E5 | SV1 | #4, #11 |
| #13 | Mastery, chọn câu, sinh câu có tham số, endpoint E6-E9 | SV2 | #5, #11 |
| #14 | Hợp đồng API v2, đăng ký router, test tích hợp | SV3 | #11 |
| #15 | Mô phỏng học sinh và kế hoạch đánh giá thí điểm | SV3 | #12, #13 |

Và sửa phụ thuộc của #8 thành: #3, #4, #5, #7, #12, #13.

**Nhật ký tiến độ:** thêm dòng

| Milestone | Trạng thái | Bằng chứng / PR |
|---|---|

### M4 — Giao diện và tích hợp end-to-end
**Phụ trách:** SV3; SV1/SV2 hỗ trợ theo module.

- [ ] M4.1 — Xác định phần UI hiện có trong `app/(root)/chat/page.tsx` và `components/`; ưu tiên tái sử dụng component.
- [ ] M4.2 — Làm rõ trạng thái upload/indexing, sinh câu hỏi, loading, empty state và lỗi.
- [ ] M4.3 — Hiển thị câu hỏi, 4 lựa chọn, đáp án/giải thích theo chính sách review của MVP.
- [ ] M4.4 — Hiển thị nguồn tham chiếu khi backend trả nguồn; nếu không có nguồn, nói rõ là chưa có thay vì tạo nguồn giả.
- [ ] M4.5 — Cho phép người dùng chấp nhận/loại câu hỏi nếu backend hỗ trợ; nếu chưa có thì triển khai phần API cần thiết trước.
- [ ] M4.6 — Chạy luồng tích hợp: upload tài liệu → truy xuất → sinh câu hỏi → hiển thị → review.
- [ ] M4.7 — Kiểm tra lỗi API, timeout, refresh trang và thao tác liên tiếp.
- [ ] M4.8 — Cập nhật ảnh chụp demo hoặc video ngắn.
- [ ] M4.9 — Chế độ làm bài cho học sinh: ẩn đáp án và giải thích đến khi nộp bài.
- [ ] M4.10 — Màn hình bài chẩn đoán (diagnostic quiz) cho học sinh mới.
- [ ] M4.11 — Hiển thị phản hồi sau mỗi câu: đúng/sai, giải thích, nguồn, thay đổi mastery.
- [ ] M4.12 — Bảng mức nắm vững theo khái niệm (`unknown / weak / learning / mastered`) và nút làm lại (reset).
- [ ] M4.13 — Hiển thị nhãn "chưa được duyệt" khi bật cấu hình `SERVE_UNREVIEWED_QUESTIONS`.

**Điều kiện hoàn thành:** một người mới có thể chạy demo theo README và hoàn thành luồng MVP mà không cần sửa code thủ công.

### M5 — Kiểm thử, sửa lỗi và đóng gói
**Phụ trách:** Cả nhóm; SV3 tổng hợp kết quả.

- [ ] M5.1 — Chạy backend tests theo README.
- [ ] M5.2 — Chạy frontend lint/test scripts thực sự có trong `package.json`.
- [ ] M5.3 — Kiểm thử thủ công ít nhất: tài liệu hợp lệ, tài liệu rỗng/lỗi, model chưa cấu hình, model trả JSON lỗi, course không có tài liệu.
- [ ] M5.4 — Kiểm tra không lộ API key, không commit file `.env` hoặc dữ liệu riêng.
- [ ] M5.5 — Ghi lại lỗi còn tồn tại; không che giấu test fail.
- [ ] M5.6 — Cập nhật README: tính năng, cài đặt, cấu hình model, chạy app, test, giới hạn và ghi công repo gốc.
- [ ] M5.7 — Chuẩn bị báo cáo: kiến trúc, phần nhóm tự làm, phần tái sử dụng, ảnh demo, kết quả test thực tế.
- [ ] M5.8 — Chạy lại kịch bản mô phỏng học sinh (`scripts/simulate_learners.py`) và ghi nhận kết quả thí điểm trung thực vào báo cáo.

**Điều kiện hoàn thành:** checklist nghiệm thu có bằng chứng; README chạy được theo môi trường nhóm; báo cáo phân biệt rõ chức năng kế thừa và phần tự phát triển.

## 5. Thứ tự phụ thuộc

```text
M0 Baseline
   ↓
M1 API/schema contract
   ↓
M2 Document & retrieval ─────┐
                             ├── M3A Adaptive (mastery, selection) ── M4 End-to-end integration
M3 Question generation ──────┘
   ↓
M5 QA, README, demo, report
```

Sau M1, SV1 và SV2 có thể làm song song. SV3 có thể khảo sát UI và tạo mock dữ liệu trong lúc chờ, nhưng chỉ tích hợp với API thật sau khi hợp đồng đã được duyệt.

## 6. Git workflow

### Nhánh
- `main`: bản ổn định, không push trực tiếp.
- `feature/setup-baseline`
- `feature/document-retrieval`
- `feature/question-generation`
- `feature/ui-integration`
- `test/e2e-mvp`
- `docs/implementation-plan`

Tên nhánh có thể bổ sung mã issue, ví dụ `feature/12-document-retrieval`.

### Quy trình cho mỗi task
1. Tạo Issue có mục tiêu, phạm vi file, tiêu chí nghiệm thu.
2. Tạo branch từ `main` mới nhất.
3. Code phần được giao; không sửa lan sang module người khác nếu chưa trao đổi.
4. Chạy test phù hợp và ghi lệnh/kết quả trong PR.
5. Mở Pull Request về `main`, liên kết Issue.
6. Một thành viên khác review; xử lý comment rồi mới merge.
7. Sau khi merge, cập nhật branch và chạy test tích hợp.

```bash
git switch main
git pull origin main
git switch -c feature/12-document-retrieval

# Sau khi sửa code
git add <cac-file-da-sua>
git commit -m "feat: improve course document retrieval"
git push -u origin feature/12-document-retrieval
```

Không dùng `git add .` một cách máy móc nếu thư mục có `.env`, dữ liệu tải lên hoặc file build.

### Quy ước commit
- `feat:` tính năng
- `fix:` sửa lỗi
- `test:` kiểm thử
- `docs:` tài liệu
- `refactor:` tái cấu trúc không đổi hành vi
- `chore:` cấu hình/công cụ

## 7. Definition of Done cho một Issue

Issue chỉ được đánh dấu hoàn thành khi:
- [ ] Đúng phạm vi đã thống nhất, không sửa ngoài phạm vi một cách âm thầm.
- [ ] Có test mới/cập nhật nếu phù hợp.
- [ ] Đã chạy test liên quan; kết quả được ghi trung thực.
- [ ] Không thêm secrets hoặc dữ liệu nhạy cảm.
- [ ] Có thông báo lỗi hợp lý cho đầu vào không hợp lệ.
- [ ] PR đã được ít nhất một thành viên khác review.
- [ ] Tài liệu được cập nhật nếu hành vi/cách chạy thay đổi.

## 8. Danh sách Issue khởi tạo đề xuất

| Issue | Tiêu đề | Owner | Phụ thuộc |
|---|---|---|---|
| #1 | Chạy baseline và ghi nhận lỗi ban đầu | SV3 điều phối, cả nhóm chạy | — |
| #2 | Chốt phạm vi MVP và hợp đồng dữ liệu | SV1 + SV2 + SV3 | #1 |
| #3 | Kiểm tra upload/extraction PDF, DOCX, TXT | SV1 | #2 |
| #4 | Kiểm tra course-scoped retrieval và nguồn | SV1 | #2 |
| #5 | Chuẩn hóa output sinh câu hỏi theo schema | SV2 | #2 |
| #6 | Kiểm tra lựa chọn, đáp án và câu hỏi trùng | SV2 | #5 |
| #7 | UI trạng thái upload/generate/error/review | SV3 | #2 |
| #8 | Tích hợp luồng upload → retrieval → generation → UI | SV3 điều phối | #3, #4, #5, #7, #12, #13 |
| #9 | Kiểm thử end-to-end và hồi quy | Cả nhóm | #8 |
| #10 | README, ảnh demo, báo cáo và ghi công | SV3 tổng hợp, cả nhóm cung cấp bằng chứng | #9 |
| #11 | Chốt thiết kế adaptive, schema v2 và chữ ký hàm | SV1 + SV2 + SV3 | #2 |
| #12 | Khái niệm, lớp dữ liệu learner/attempt và endpoint E1-E5 | SV1 | #4, #11 |
| #13 | Mastery, chọn câu, sinh câu có tham số, endpoint E6-E9 | SV2 | #5, #11 |
| #14 | Hợp đồng API v2, đăng ký router, test tích hợp | SV3 | #11 |
| #15 | Mô phỏng học sinh và kế hoạch đánh giá thí điểm | SV3 | #12, #13 |

> Số Issue ở bảng là ID kế hoạch minh họa; GitHub sẽ tự cấp số thực khi tạo Issue.

## 9. Cấu trúc tài liệu nhóm đề xuất

```text
docs/
├── IMPLEMENTATION_PLAN.md
├── API_CONTRACT.md
├── TEST_PLAN.md
├── ARCHITECTURE.md
└── meeting-notes/
    └── decisions.md
```

## 10. Nguồn và ghi công

- Dự án tham khảo: https://github.com/cRED-f/QuestGen-AI-Agent
- Đọc README và LICENSE của repo gốc trước khi phân phối bản fork.
- Trong báo cáo, phân biệt:
  1. Thành phần được kế thừa/tái sử dụng.
  2. Thành phần nhóm chỉnh sửa.
  3. Thành phần nhóm tự xây dựng.
  4. Kiểm thử đã chạy và kết quả thực tế.

---

## Nhật ký tiến độ

Cập nhật bảng dưới đây trong quá trình làm; không đánh dấu hoàn thành trước khi có bằng chứng.

| Milestone | Trạng thái | Bằng chứng / PR |
|---|---|---|
| M0 — Baseline | Not started | |
| M1 — Contract | Completed | `docs/API_CONTRACT.md`, `backend/schemas.py`, 6/6 tests passed in `tests/test_contract.py` |
| M2 — Retrieval | Completed | PR #11 (SV1), commit `b192363` (SV2), PR #12 (SV3), `backend/documents.py`, `backend/ingestion.py`, `backend/retrieval.py` |
| M3 — Generation | In Progress | `backend/mcq_parsing.py`, validation & adapter v2 |
| M3A — Adaptive | Not started | Hợp đồng schema v2, `mastery.py`, `selection.py`, `learner_store.py` |
| M4 — Integration | Not started | |
| M5 — QA & demo | Not started | |
