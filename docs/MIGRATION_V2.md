# Bản vá QuizForge-AI: ingestion / embeddings / vector store / schemas

Đặt các file vào đúng chỗ: `backend/*.py` thay/thêm vào package `backend`, `tests/*` ở thư mục gốc dự án.

## Cần làm sau khi áp dụng (BẮT BUỘC)
1. **Re-index toàn bộ tài liệu.** `chunk_id` đã đổi (có `course_id`) và vector đã đổi (có prefix query/document),
   nên dữ liệu cũ không dùng lại được. Collection mặc định đổi từ `quizforge_chunks_v1` sang `quizforge_chunks_v2`,
   nên bản cũ không gây lỗi "sai model", chỉ bị bỏ lại. Xóa thư mục Chroma cũ nếu không cần nữa.
2. Chạy `pytest tests/` sau khi cài `pydantic httpx pytest chromadb`. `tests/test_vector_store.py` là bài kiểm chứng
   cosine thật trên đúng phiên bản Chroma bạn dùng. **Hãy ghim version chromadb** sau khi test qua.

## Đã sửa
| # | Lỗi | File | Cách sửa |
|---|-----|------|----------|
| 1 | Trang < 10 ký tự làm lỗi cả tài liệu | ingestion | Bỏ qua trang đó (log debug) |
| 2 | `chunk_id` thiếu `course_id` | ingestion | `make_chunk_id(course_id, doc_id, index)`, mã hóa JSON để không nhập nhằng dấu `:` |
| 3 | Re-index ra 0 chunk, chunk cũ còn | ingestion | Gọi `delete_document` khi không có chunk; kiểm tra model trước khi embed |
| 4 | Không có prefix query/document | embeddings | Prefix theo model (embeddinggemma, nomic-embed-text, mxbai-embed-large), ghi đè bằng env `QUIZFORGE_EMBEDDING_QUERY_PREFIX` / `..._DOCUMENT_PREFIX`; digest prefix nằm trong `model_name` |
| 5 | Kiểm tra cosine phụ thuộc phiên bản Chroma | vector_store | Khóa metadata riêng `distance_metric`, kiểm cả `hnsw:space` và `collection.configuration` nếu có, fallback sang `configuration=` khi tạo collection |
| 6a | Unicode NFD/NFC | ingestion | Chuẩn hóa NFC trước khi chia chunk |
| 6b | Lỗi Ollama không có nội dung | embeddings | Thông báo kèm status và body (cắt 500 ký tự); env sai nêu rõ tên biến |
| 6c | Mỗi lần index tạo client Chroma mới | vector_store | `get_vector_store()` cache theo (path, collection, model) |
| S1 | ID đáp án chỉ validate | schemas | `OptionId` chuẩn hóa + `Literal["A".."D"]`; `type: Literal["mcq"]` |
| S2 | Adapter chỉ khớp theo text | schemas, mcq_parsing | Nhận "B", "(b)", "B. text", text đầy đủ; bóc tiền tố "A. " khi cả 4 option đều có; chữ cái mâu thuẫn với text thì báo lỗi |
| S3 | Câu không nguồn vẫn ACCEPTED | schemas | ACCEPTED cần >= 1 `source_ref` có snippet; `sid` không tìm thấy thì báo lỗi (`strict_sources=False` để chỉ cảnh báo); `validate_assignment=True` |
| S4 | Nhãn Bloom/độ khó sai bị đổi âm thầm | schemas | Log warning (hoặc `strict_labels=True` thì raise); nhận Enum và nhãn tiếng Việt |
| S5 | Đáp án đúng thiên vị vị trí | schemas | `shuffle_options` xác định theo `question.id`; bỏ qua khi có option kiểu "Cả A và B" |
| S6 | Docstring "bi-directional" | schemas | Thêm `target_to_questgen` (mất thông tin: chỉ giữ chunk id) |
| M1 | `SourceReference` thiếu chunk_id; `RetrievalResult` mất thông tin | schemas, vector_store, retrieval | `SourceReference.chunk_id`, `RetrievedChunk`, `RetrievalResult.chunks`, `search/get_chunks/get_neighbors`, `retrieve_context` |

Bổ sung (không phải sửa lỗi): `Concept`, `QuizRequest`, `AttemptRecord`, `ConceptMastery`, và `concept_ids`/`generator_model`/`prompt_version`/`created_at` trên câu hỏi.

## Thay đổi hành vi cần biết
- `questgen_to_target_schema` mặc định **shuffle** và **strict_sources**. Truyền `shuffle=False`, `strict_sources=False` để giữ cách cũ.
- `question` và `explanation` yêu cầu >= 10 ký tự (trước là 5): chỉnh `MIN_QUESTION_CHARS`, `MIN_EXPLANATION_CHARS`.
- `model_name` của Ollama có thêm hậu tố `#p<hash>` khi dùng prefix.

## Chưa làm
- Gắn concept/section cho từng chunk (Chroma metadata không lưu list, cần JSON string hoặc bảng riêng).
- Thuật toán mastery và chọn câu hỏi tiếp theo.
- Nhiều worker cùng ghi một thư mục Chroma: cache chỉ có tác dụng trong một process, nên dùng Chroma server.

## Mức độ kiểm chứng
Offline, không cài được pydantic/httpx/chromadb. Đã chạy thật: `mcq_parsing` (25 case). Đã chạy với bản giả lập (stub)
của pydantic/httpx: ingestion, embeddings, retrieval (22 test). Chưa chạy: `schemas.py` thật, `vector_store.py` với Chroma thật.
