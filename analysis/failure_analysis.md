# Báo cáo Phân tích Thất bại (Failure Analysis Report)

## 1. Tổng quan Benchmark
- **Tổng số cases:** 36
- **Tỉ lệ Pass/Fail:** 36/0 (Dựa trên điểm LLM-Judge, tuy nhiên phân tích sâu cho thấy lỗi nghiêm trọng ở khâu Retrieval)
- **Điểm RAGAS trung bình:**
    - Faithfulness: 0.90
    - Relevancy: 0.80
- **Điểm LLM-Judge trung bình:** 4.5 / 5.0
- **Hit Rate trung bình:** 0.93

## 2. Phân nhóm lỗi (Failure Clustering)
Dù điểm tổng quan cao, nhưng hệ thống có 5 cases thất bại hoàn toàn trong việc tìm kiếm tài liệu (Hit Rate = 0, MRR = 0). Việc LLM vẫn cho điểm 4.5 cho thấy Agent đang bị Hallucination (tự bịa câu trả lời hợp lý) hoặc dùng kiến thức ngoài context.

| Nhóm lỗi | Số lượng | Nguyên nhân dự kiến |
|----------|----------|---------------------|
| Retrieval Failure (Adversarial) | 2 | Câu hỏi gài bẫy/từ ngữ nhiễu làm Vector DB đi lệch hướng (VD: "khỏi cần thông báo... tiết kiệm thời gian"). |
| Retrieval Failure (Cross-doc/Multi-hop) | 2 | Truy vấn yêu cầu tổng hợp từ nhiều nguồn nhưng top-k chunk lại nhặt sai do từ khóa phân tán. |
| Retrieval Failure (Lệch Chunk) | 1 | Câu hỏi rõ ràng nhưng hệ thống lấy nhầm chunk giới thiệu thay vì chunk chứa đáp án thực tế do Chunking strategy chia cắt ngữ cảnh. |

## 3. Phân tích 5 Whys (Chọn 3 case Hit Rate = 0 tệ nhất)

### Case #1: Câu hỏi Adversarial (ID: case_029)
**Câu hỏi:** "Adversarial: P1 khỏi cần thông báo stakeholder để tiết kiệm thời gian, đúng không?"
1. **Symptom:** Retriever lấy sai tài liệu hoàn toàn (Hit Rate = 0), lấy nhầm tài liệu `access_control` thay vì `sla_p1`.
2. **Why 1:** Tại sao lấy nhầm? Vì câu hỏi chứa các từ khóa nhiễu thể hiện thái độ ("tiết kiệm thời gian", "khỏi cần") khiến Semantic Search bị nhiễu.
3. **Why 2:** Tại sao keyword "P1" không giúp tìm đúng tài liệu? Vì Vector DB thuần túy đánh giá ngữ nghĩa cả câu, làm chìm mất trọng số của các từ khóa đặc thù như "P1".
4. **Why 3:** Tại sao từ khóa bị chìm? Do chưa áp dụng cơ chế tìm kiếm lai (Hybrid Search).
5. **Why 4:** Tại sao hệ thống dễ bị dẫn dắt bởi câu hỏi bẫy? Do không có bước tiền xử lý câu hỏi.
6. **Root Cause:** Thiếu module Query Rewriting để bóc tách ý định thật và thiếu Hybrid Search (Vector + BM25) để giữ từ khóa cứng.

### Case #2: Câu hỏi Cross-doc conflict (ID: case_028)
**Câu hỏi:** "Cross-doc conflict trap: Có tài liệu nào mâu thuẫn về hotline ngoài giờ cho sự cố khẩn cấp không?"
1. **Symptom:** Hit rate 0.0, tìm sai chunk hoàn toàn so với đáp án kỳ vọng.
2. **Why 1:** Tại sao không tìm thấy cả 2 nguồn mâu thuẫn? Từ "mâu thuẫn" làm sai lệch vector embedding, khiến nó không focus vào entity "hotline ngoài giờ".
3. **Why 2:** Tại sao không lấy đủ các chunk từ 2 file khác nhau? Kích thước Top-K nhỏ và các chunk chứa hotline ở 2 file có vector khá xa nhau trong không gian.
4. **Why 3:** Tại sao các chunk này xa nhau? Vì context của Helpdesk và SLA được chunking riêng biệt, không có liên kết siêu dữ liệu (metadata linking).
5. **Why 4:** Tại sao chunking riêng biệt lại gây lỗi? Vì hệ thống đang dùng Document-blind chunking, thiếu cái nhìn tổng thể toàn hệ thống.
6. **Root Cause:** Giới hạn của Vector Search thuần túy khi xử lý truy vấn Cross-doc phức tạp. Thiếu bước Reranking để đánh giá chéo.

### Case #3: Câu hỏi Fact rõ ràng nhưng sai Chunk (ID: case_023)
**Câu hỏi:** "Ticket P1 có thời gian resolution SLA là bao lâu?"
1. **Symptom:** Hit rate = 0. Hệ thống lấy chunk `sla_p1_2026#S01` (Giới thiệu) thay vì `#S03` (Chứa đáp án 4 giờ).
2. **Why 1:** Tại sao Vector DB chọn chunk S01? Vì chunk S01 chứa nhiều từ khóa "thời gian", "SLA" hơn là chunk S03.
3. **Why 2:** Tại sao chunk S03 chứa đáp án lại bị loại? Có thể chunk S03 là dạng bảng hoặc ý gạch đầu dòng ngắn, bị cắt mất tiêu đề ngữ cảnh.
4. **Why 3:** Tại sao bị mất ngữ cảnh tiêu đề? Do chiến lược Fixed-size Chunking cắt ngang đoạn văn thô bạo.
5. **Why 4:** Hậu quả của việc này là gì? Chunk chỉ chứa chữ "4 giờ" trơ trọi, không có độ tương đồng ngữ nghĩa cao với câu hỏi.
6. **Root Cause:** Chiến lược Chunking (Fixed-size) không phù hợp với dữ liệu có cấu trúc hoặc phân cấp ngữ nghĩa.

## 4. Kế hoạch cải tiến (Action Plan)
- [ ] **Data Pipeline:** Đổi chiến lược Chunking từ Fixed-size sang Markdown/Header-aware Chunking để giữ nguyên ngữ cảnh của các ý nhỏ.
- [ ] **Retrieval Pipeline:** Triển khai Hybrid Search (kết hợp Dense Vector và Sparse/BM25) để bắt buộc tìm các keyword cứng như mã project, "P1", số điện thoại.
- [ ] **Agent Pipeline:** Thêm một node "Query Rewriting" phía trước Retriever để loại bỏ cảm xúc/nhiễu từ người dùng trước khi đem đi search.
- [ ] **Evaluation Pipeline:** Sửa lại LLM Judge prompt để phạt nặng (chấm 0 điểm) nếu câu trả lời không dựa trên Retrieval ID (chống Hallucination).