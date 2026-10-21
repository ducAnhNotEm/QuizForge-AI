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

**Không làm trong MVP:** tài khoản nhiều vai trò phức tạp, triển khai production, thanh toán, hỗ trợ mọi định dạng file, tự động khẳng định câu hỏi đúng tuyệt đối. Ưu tiên dùng chức năng sẵn có thay vì viết lại toàn bộ.

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
| **SV1** | Tài liệu và truy xuất (RAG) | `backend/documents.py`, `backend/ingestion.py`, phần liên quan trong `backend/course_tools.py`; test tài liệu tương ứng | Upload → trích xuất → chunk/index → lấy được đoạn nguồn phù hợp |
| **SV2** | Sinh câu hỏi và kiểm tra chất lượng | `backend/generation.py`, `backend/exam_builder.py`, `backend/exam_context.py`, test generation/exam liên quan | Sinh câu hỏi theo schema, kiểm tra dữ liệu đầu ra, có luồng review |
| **SV3** | UI, tích hợp và QA điều phối | `app/(root)/chat/page.tsx`, UI components cần thiết, frontend tests, README/demo; điều phối tích hợp | Luồng người dùng hoàn chỉnh, trạng thái loading/error, hướng dẫn chạy và demo |

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

- [ ] M1.1 — Chốt luồng: chọn môn/tài liệu → upload/index → yêu cầu sinh câu hỏi → xem nguồn → review câu hỏi.
- [ ] M1.2 — Chốt schema câu hỏi và response API trước khi code song song.
- [ ] M1.3 — Chốt cách thể hiện lỗi: file không hỗ trợ, tài liệu rỗng, chưa cấu hình model, model timeout, đầu ra sai schema.
- [ ] M1.4 — Thêm `docs/API_CONTRACT.md` mô tả endpoint thực tế sau khi đối chiếu `backend/app.py`; không tự đặt endpoint rồi coi là đã tồn tại.
- [ ] M1.5 — Tạo fixture tài liệu nhỏ, không chứa thông tin nhạy cảm, dùng chung cho test.

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
Schema trên là **hợp đồng mục tiêu**; cần ánh xạ sang cấu trúc hiện có trước khi sửa để tránh phá vỡ tương thích.

**Điều kiện hoàn thành:** SV1, SV2, SV3 cùng duyệt hợp đồng; có ít nhất một test/fixture minh họa dữ liệu đầu vào và đầu ra.

### M2 — Tài liệu và retrieval
**Phụ trách:** SV1.

- [ ] M2.1 — Lần theo pipeline hiện có trong `backend/documents.py` và `backend/ingestion.py`.
- [ ] M2.2 — Xác nhận upload PDF/DOCX/TXT hoạt động; không viết lại nếu tính năng đã ổn.
- [ ] M2.3 — Kiểm tra xử lý file rỗng, lỗi đọc file, file trùng và tài liệu nhiều trang.
- [ ] M2.4 — Xác nhận retrieval bị giới hạn trong môn/course được chọn, không lấy nhầm tài liệu từ course khác.
- [ ] M2.5 — Kiểm tra nguồn/page citation nếu đã được hỗ trợ; không bịa số trang khi thiếu metadata.
- [ ] M2.6 — Viết hoặc cập nhật unit tests cho các trường hợp thành công và lỗi.
- [ ] M2.7 — Bàn giao mô tả đầu vào/đầu ra của retrieval cho SV2.

**Điều kiện hoàn thành:** với fixture đã chốt, truy xuất trả về các đoạn có liên quan và thông tin nguồn hiện có; các trường hợp lỗi được xử lý rõ ràng.

### M3 — Sinh câu hỏi và kiểm soát đầu ra
**Phụ trách:** SV2.

- [ ] M3.1 — Lần theo pipeline hiện có trong `backend/generation.py`, `backend/exam_builder.py`, `backend/exam_context.py`.
- [ ] M3.2 — Tạo câu hỏi từ context được retrieval cung cấp, không cho model tự coi kiến thức ngoài tài liệu là bằng chứng.
- [ ] M3.3 — Chuẩn hóa đầu ra theo schema đã thống nhất; xử lý JSON lỗi/thiếu trường/loại dữ liệu sai.
- [ ] M3.4 — Kiểm tra đủ 4 lựa chọn, ID lựa chọn không trùng, đáp án đúng nằm trong lựa chọn.
- [ ] M3.5 — Thêm kiểm tra câu hỏi trùng lặp ở mức cơ bản và phát hiện câu hỏi/đáp án rỗng.
- [ ] M3.6 — Giữ trạng thái `draft` cho câu hỏi mới; người dùng phải xem lại trước khi coi là đã duyệt.
- [ ] M3.7 — Thêm test cho đầu ra hợp lệ và các lỗi model thường gặp.
- [ ] M3.8 — Ghi nhận giới hạn: kiểm tra schema không chứng minh nội dung học thuật đúng tuyệt đối.

**Điều kiện hoàn thành:** với context mẫu, pipeline trả về danh sách câu hỏi theo schema hoặc báo lỗi có kiểm soát; không làm ứng dụng sập khi model trả dữ liệu không hợp lệ.

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

**Điều kiện hoàn thành:** checklist nghiệm thu có bằng chứng; README chạy được theo môi trường nhóm; báo cáo phân biệt rõ chức năng kế thừa và phần tự phát triển.

## 5. Thứ tự phụ thuộc

```text
M0 Baseline
   ↓
M1 API/schema contract
   ↓
M2 Document & retrieval ─────┐
                             ├── M4 End-to-end integration
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
| #8 | Tích hợp luồng upload → retrieval → generation → UI | SV3 điều phối | #3, #4, #5, #7 |
| #9 | Kiểm thử end-to-end và hồi quy | Cả nhóm | #8 |
| #10 | README, ảnh demo, báo cáo và ghi công | SV3 tổng hợp, cả nhóm cung cấp bằng chứng | #9 |

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
| M1 — Contract | Not started | |
| M2 — Retrieval | Not started | |
| M3 — Generation | Not started | |
| M4 — Integration | Not started | |
| M5 — QA & demo | Not started | |
