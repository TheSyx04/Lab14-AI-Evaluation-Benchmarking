# Báo cáo Phân tích Thất bại (Failure Analysis Report)

## 1. Tổng quan Benchmark
- **Tổng số cases:** 72
- **Tỉ lệ Pass/Fail:** 72/0 (theo Judge nhưng Retrieval có 5/72 case thất bại hoàn toàn (6.94%, Hit Rate = 0 và MRR = 0))
- **Điểm RAGAS trung bình:**
    - Faithfulness: 0.90
    - Relevancy: 0.80
- **Điểm LLM-Judge trung bình:** 4.5 / 5.0
- **Hit Rate trung bình:** 0.9306
- **MRR trung bình:** 0.8542
- **Agreement Rate trung bình:** 0.80

## 2. Phân nhóm lỗi (Failure Clustering)
Dù điểm tổng quan cao, hệ thống có 5 cases thất bại hoàn toàn ở Retrieval (Hit Rate = 0, MRR = 0): `case_039`, `case_047`, `case_056`, `case_062`, `case_071`.
Việc Judge vẫn chấm cao cho toàn bộ case cho thấy có nguy cơ Agent trả lời hợp lý theo pattern ngôn ngữ nhưng không bám đúng context truy xuất.

| Nhóm lỗi | Số lượng | Nguyên nhân dự kiến |
|----------|----------|---------------------|
| Retrieval Failure (Adversarial) | 1 | Ngôn ngữ phủ định/gài bẫy làm truy vấn lệch khỏi keyword cứng (P1, stakeholder). |
| Retrieval Failure (Cross-doc/Multi-hop) | 2 | Truy vấn cần tổng hợp nhiều nguồn nhưng top-k không kéo đủ cả hai tài liệu liên quan. |
| Retrieval Failure (Single-hop nhưng trượt chunk đích) | 2 | Câu hỏi rõ ràng nhưng retriever trả về chunk liên quan yếu hoặc thiên về phần mô tả chung. |

## 3. Phân tích 5 Whys (Chọn 3 case Hit Rate = 0 tệ nhất)

### Case #1: Câu hỏi Adversarial (ID: case_047)
**Câu hỏi:** "Adversarial: P1 khỏi cần thông báo stakeholder để tiết kiệm thời gian, đúng không?"
1. **Symptom:** Retriever lấy sai tài liệu hoàn toàn (Hit Rate = 0), lấy nhầm tài liệu `access_control` thay vì `sla_p1`.
2. **Why 1:** Tại sao lấy nhầm? Vì câu hỏi chứa các từ khóa nhiễu thể hiện thái độ ("tiết kiệm thời gian", "khỏi cần") khiến Semantic Search bị nhiễu.
3. **Why 2:** Tại sao keyword "P1" không giúp tìm đúng tài liệu? Vì Vector DB thuần túy đánh giá ngữ nghĩa cả câu, làm chìm mất trọng số của các từ khóa đặc thù như "P1".
4. **Why 3:** Tại sao từ khóa bị chìm? Do chưa áp dụng cơ chế tìm kiếm lai (Hybrid Search).
5. **Why 4:** Tại sao hệ thống dễ bị dẫn dắt bởi câu hỏi bẫy? Do không có bước tiền xử lý câu hỏi.
6. **Root Cause:** Thiếu module Query Rewriting để bóc tách ý định thật và thiếu Hybrid Search (Vector + BM25) để giữ từ khóa cứng.

### Case #2: Câu hỏi Cross-doc conflict (ID: case_062)
**Câu hỏi:** "Cross-doc conflict trap: Có tài liệu nào mâu thuẫn về hotline ngoài giờ cho sự cố khẩn cấp không?"
1. **Symptom:** Hit rate 0.0, tìm sai chunk hoàn toàn so với đáp án kỳ vọng.
2. **Why 1:** Tại sao không tìm thấy cả 2 nguồn mâu thuẫn? Từ "mâu thuẫn" làm sai lệch vector embedding, khiến nó không focus vào entity "hotline ngoài giờ".
3. **Why 2:** Tại sao không lấy đủ các chunk từ 2 file khác nhau? Kích thước Top-K nhỏ và các chunk chứa hotline ở 2 file có vector khá xa nhau trong không gian.
4. **Why 3:** Tại sao các chunk này xa nhau? Vì context của Helpdesk và SLA được chunking riêng biệt, không có liên kết siêu dữ liệu (metadata linking).
5. **Why 4:** Tại sao chunking riêng biệt lại gây lỗi? Vì hệ thống đang dùng Document-blind chunking, thiếu cái nhìn tổng thể toàn hệ thống.
6. **Root Cause:** Giới hạn của Vector Search thuần túy khi xử lý truy vấn Cross-doc phức tạp. Thiếu bước Reranking để đánh giá chéo.

### Case #3: Câu hỏi Fact rõ ràng nhưng sai Chunk (ID: case_039)
**Câu hỏi:** "Ticket P1 có thời gian resolution SLA là bao lâu?"
1. **Symptom:** Hit rate = 0. Retriever không trả về chunk đích `sla_p1_2026#S03`.
2. **Why 1:** Tại sao trượt chunk đích? Truy vấn ngắn dạng fact bị cạnh tranh bởi các chunk tổng quát cũng chứa từ "P1" và "SLA".
3. **Why 2:** Tại sao chunk tổng quát thắng điểm? Retriever chưa có bước reranking theo độ khớp factual entity (resolution/4 giờ).
4. **Why 3:** Tại sao không có tín hiệu entity mạnh? Truy vấn chưa được chuẩn hóa từ khóa cứng (resolution, first response, escalation).
5. **Why 4:** Tại sao điều này lặp lại? Pipeline chưa có lớp lexical match bổ sung cho dense retrieval.
6. **Root Cause:** Thiếu Hybrid Retrieval + Reranking theo thực thể khiến câu hỏi fact ngắn dễ trượt chunk đáp án.

## 4. Kế hoạch cải tiến (Action Plan)
- [ ] **Data Pipeline:** Giữ Header-aware chunking hiện tại, bổ sung metadata linking giữa các chunk liên quan cross-doc (ví dụ hotline, P1, escalation).
- [ ] **Retrieval Pipeline:** Triển khai Hybrid Search (kết hợp Dense Vector và Sparse/BM25) để bắt buộc tìm các keyword cứng như mã project, "P1", số điện thoại.
- [ ] **Agent Pipeline:** Thêm một node "Query Rewriting" phía trước Retriever để loại bỏ cảm xúc/nhiễu từ người dùng trước khi đem đi search.
- [ ] **Evaluation Pipeline:** Sửa lại LLM Judge prompt để phạt nặng (chấm 0 điểm) nếu câu trả lời không dựa trên Retrieval ID (chống Hallucination).