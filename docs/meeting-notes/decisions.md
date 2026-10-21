# BIÊN BẢN QUYẾT ĐỊNH PHẠM VI MVP (M0.8 & M1.1)
# Dự án: QuizForge-AI

- **Thời gian:** 2026-10-21
- **Thành phần tham gia:** SV1, SV2, SV3
- **Chủ trì:** SV3

---

## 1. Quyết định về Phạm vi Sản phẩm (Scope)

### ✅ Những tính năng BẮT BUỘC trong MVP:
1. **Quản lý không gian học:** Tạo hoặc chọn môn học (`course_id`).
2. **Tải lên & Xử lý tài liệu:**
   - Định dạng hỗ trợ: `.pdf`, `.docx`, `.txt`.
   - Giới hạn dung lượng: Tối đa 20MB / file.
   - Báo lỗi rõ ràng nếu file rỗng hoặc không đọc được.
3. **Truy xuất nội dung (RAG):**
   - Chỉ tìm kiếm tài liệu thuộc đúng môn học đã chọn (`course_scoped`).
   - Có nguồn trích dẫn (`source_refs`: tên file, số trang, trích đoạn).
4. **Sinh câu hỏi trắc nghiệm (MCQ):**
   - Mỗi câu gồm đúng 4 lựa chọn (A, B, C, D).
   - 1 đáp án đúng duy nhất, có giải thích ngắn gọn.
   - Bám sát context tài liệu, không bịa kiến thức bên ngoài.
5. **Duyệt câu hỏi (Review flow):**
   - Câu hỏi sinh ra mặc định mang trạng thái `draft`.
   - Người dùng có thể nhấn `Accept` (Lưu lại) hoặc `Reject` (Loại bỏ).

---

### ❌ Những tính năng TẠM HOÃN (Out of MVP Scope):
1. Hệ thống phân quyền nhiều vai trò phức tạp (Admin, Giáo viên, Sinh viên).
2. Tích hợp cổng thanh toán.
3. Xuất file đề thi PDF/Word có định dạng phức tạp.
4. Tự động chấm điểm trắc nghiệm trực tuyến thời gian thực (để dành cho giai đoạn sau).
5. OCR tài liệu scan dạng hình ảnh chất lượng thấp.

---

## 2. Thống nhất Kỹ thuật & Nguyên tắc Làm việc (Git & Code)
1. Tuyệt đối không commit file `.env`, API Key hay dữ liệu bài học có bản quyền lên GitHub.
2. Không push thẳng vào branch `main`. Mọi tính năng phải qua Pull Request và có ít nhất 1 người review.
3. Các thành viên tuân thủ nghiêm ngặt hợp đồng dữ liệu trong `docs/API_CONTRACT.md`.
