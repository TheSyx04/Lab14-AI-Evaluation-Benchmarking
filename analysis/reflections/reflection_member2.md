# Reflection – Member 2: Retrieval Metrics Engineer

**Họ và tên / MSSV:** 2A202600478  
**Vai trò:** Retrieval Metrics Engineer  
**Phụ trách:** `engine/retrieval_eval.py`, tích hợp retriever adapter với Vector DB, chuẩn hóa ID giữa retriever và golden set, gắn kết retrieval metrics vào pipeline.

---

## 1. Vai trò & Trách nhiệm

- Hoàn thiện `engine/retrieval_eval.py`: implement `calculate_hit_rate`, `calculate_mrr`, `evaluate_batch`.
- Tích hợp retriever TF-IDF sparse vào `agent/main_agent.py` sử dụng `data/vector_db_local.json`.
- Chuẩn hóa format chunk ID (`doc_id#Sxx`) để đảm bảo mapping đúng giữa `expected_retrieval_ids` và `retrieved_ids`.
- Phối hợp với Member 4 (Runner) để gắn retrieval metrics vào pipeline runner.
- Kiểm tra mapping đúng cho tối thiểu 10 case đầu (sample mapping report).

---

## 2. Công việc đã thực hiện

### 2.1 Hoàn thiện `engine/retrieval_eval.py`

- **`calculate_hit_rate(expected_ids, retrieved_ids, top_k)`**: Kiểm tra xem trong top-k kết quả retrieved có chứa ít nhất 1 ID khớp với expected hay không. Trả về `1.0` (hit) hoặc `0.0` (miss).
- **`calculate_mrr(expected_ids, retrieved_ids)`**: Tính Mean Reciprocal Rank theo công thức `1 / rank` tại vị trí đầu tiên có kết quả đúng. Trả về `0.0` nếu không có kết quả khớp.
- **`_normalize_id` / `_normalize_ids`**: Chuẩn hóa ID về lowercase, loại bỏ khoảng trắng và trùng lặp – đảm bảo so sánh ổn định dù ID được ghi theo case khác nhau.
- **`_ensure_ids`**: Fallback thông minh khi response không có `retrieved_ids` trực tiếp: lần lượt thử `response.retrieved_ids` → `metadata.sources` → `[]`.
- **`evaluate_batch`**: Không còn placeholder. Chạy đánh giá toàn bộ dataset, trả về `avg_hit_rate`, `avg_mrr`, `sample_mapping_report` (10 case đầu), `evaluated_cases`.

### 2.2 Tích hợp retriever vào `agent/main_agent.py`

- Load `data/vector_db_local.json` (TF-IDF sparse index) ngay khi khởi tạo agent.
- Implement `_query_sparse_vector`: tokenize câu hỏi, tính TF-IDF weight cho từng token, trả về sparse vector.
- Implement `_cosine`: tính cosine similarity giữa query vector và document vector theo norm đã tính sẵn.
- Implement `_simple_retrieve`: rank toàn bộ chunk, trả về top-3 `chunk_id` theo format `doc_id#Sxx`.
- Fallback an toàn: nếu Vector DB chưa có hoặc bị lỗi, trả về một chunk mặc định thay vì raise exception.

### 2.3 Phối hợp tích hợp vào `engine/runner.py` (với Member 4)

- `run_single_test()` gọi `RetrievalEvaluator.calculate_hit_rate()` và `.calculate_mrr()` cho từng case.
- Kết quả retrieval được nhúng vào `ragas_scores["retrieval"]` gồm: `hit_rate`, `mrr`, `expected_retrieval_ids`, `retrieved_ids`.
- Sau `run_all()`, gọi `evaluate_batch()` để sinh `retrieval_mapping_check` cho 10 case đầu phục vụ audit.

---

## 3. Quyết định kỹ thuật quan trọng

| Quyết định | Lý do |
|---|---|
| Dùng TF-IDF sparse thay vì dense embedding | Tái sử dụng `vector_db_local.json` đã có từ lab trước, không tốn chi phí rebuild embedding |
| Normalize ID về lowercase | Tránh lỗi so sánh `access_control_sop#S03` ≠ `access_control_sop#s03` do case khác nhau |
| Fallback 3 tầng trong `_ensure_ids` | Agent từ các lab trước có thể trả format khác nhau, fallback đảm bảo pipeline không bị crash |
| Trả về top-3 chunk ID | Phù hợp với `top_k=3` mặc định của `RetrievalEvaluator`, nhất quán trong toàn pipeline |
| Sample mapping report 10 case đầu | Đủ để kiểm tra thủ công chất lượng mapping mà không làm nặng output |

---

## 4. Khó khăn & Cách giải quyết

### Khó khăn 1: Không nhất quán format chunk ID
- Golden set ghi `access_control_sop#S03` (uppercase S), retriever lại trả về lowercase hoặc khác case.
- **Giải pháp**: Implement `_normalize_ids()` chuẩn hóa tất cả về lowercase trước khi so sánh, áp dụng cả ở `calculate_hit_rate` lẫn `evaluate_batch`.

### Khó khăn 2: Agent cũ không trả về `retrieved_ids`
- Một số test case dùng agent scaffold cũ không có field `retrieved_ids` trong response.
- **Giải pháp**: Implement `_ensure_ids()` với fallback thử `metadata.sources`, nếu không có thì trả về `[]` – coi như retrieval miss thay vì crash.

### Khó khăn 3: Windows console lỗi encoding emoji
- Khi chạy `python main.py` trên Windows, console không hỗ trợ UTF-8 emoji dẫn đến lỗi UnicodeEncodeError.
- **Giải pháp**: Chạy với biến môi trường `PYTHONIOENCODING=utf-8` để ép console dùng UTF-8.

---

## 5. Kết quả đạt được

| Metric | Giá trị |
|---|---|
| `avg_hit_rate` (toàn dataset 72 cases) | **0.9306 (93.06%)** |
| `avg_mrr` | Có trong từng case, tích hợp vào summary |
| Mapping report | ✅ 10 case đầu đã kiểm tra khớp |
| Placeholder còn lại | **0** – `evaluate_batch` chạy thật hoàn toàn |

---

## 6. Bài học rút ra

1. **ID consistency là nền tảng của Retrieval Evaluation**: Nếu format ID không đồng nhất giữa golden set và retriever output, mọi metric đều vô nghĩa – hit rate = 0% dù retriever hoạt động đúng.
2. **Tái sử dụng thay vì rebuild**: Vector DB TF-IDF từ lab trước hoàn toàn có thể tái dùng sau khi chuẩn hóa ID, tiết kiệm đáng kể thời gian và chi phí.
3. **Defensive coding trong pipeline**: Các module trong pipeline thực cần fallback rõ ràng ở mọi bước, đặc biệt khi input có thể đến từ nhiều phiên bản agent khác nhau.
4. **Tách Retrieval metrics khỏi Generation metrics**: Hit Rate và MRR đo chất lượng tìm kiếm, hoàn toàn độc lập với chất lượng câu trả lời – không nên gộp chung khi phân tích.

---

## 7. Đề xuất cải tiến

- [ ] Nâng cấp từ TF-IDF sparse lên Hybrid Search (TF-IDF + dense embedding) để cải thiện recall trên hard cases.
- [ ] Thêm Reranking step (cross-encoder) sau retrieval để cải thiện MRR.
- [ ] Mở rộng `sample_mapping_report` thành toàn bộ dataset (không chỉ 10 case) và lưu ra file riêng để audit dễ hơn.
- [ ] Thêm metric `precision@k` bên cạnh `hit_rate` và `mrr` để đánh giá toàn diện hơn.
- [ ] Tự động phát hiện format ID mismatch và cảnh báo ngay khi load golden set.
