# Reflection - TranSyMinhQuan (2A202600308)

## 1. Vai trò và phạm vi đóng góp
- Vai trò chính: Data/QA support trong pipeline Evaluation Factory.
- Phạm vi công việc đã tham gia:
  - Thiết kế và mở rộng Golden Dataset (>= 50 cases) với hard cases.
  - Chuẩn hóa mapping `expected_retrieval_ids` để phục vụ Hit Rate/MRR.
  - Hỗ trợ kiểm thử benchmark và đối chiếu kết quả trong `reports/summary.json`, `reports/benchmark_results.json`.
  - Đồng bộ báo cáo `analysis/failure_analysis.md` theo đúng số case và case ID thực tế sau khi chạy benchmark.

## 2. Engineering Contribution
- Đóng góp kỹ thuật cụ thể:
  - Xây dựng/tinh chỉnh dữ liệu test để bao phủ các nhóm case: fact, adversarial, out-of-context, ambiguous, conflict, multi-hop.
  - Bảo đảm chất lượng dataset ở mức có thể chấm retrieval bằng số liệu định lượng thay vì cảm tính.
  - Kiểm tra tính nhất quán giữa benchmark output và failure report để tránh lệch số liệu/case ID.
- Giá trị mang lại cho team:
  - Giảm rủi ro nộp báo cáo "đẹp nhưng sai dữ liệu".
  - Tăng khả năng debug nguyên nhân lỗi retrieval qua case-level evidence.

## 3. Technical Depth

### 3.1 MRR và ý nghĩa thực tế
- MRR (Mean Reciprocal Rank) đo vị trí xuất hiện của tài liệu đúng đầu tiên trong danh sách retrieved.
- Nếu tài liệu đúng ở vị trí 1 thì điểm là 1.0; ở vị trí 2 thì 0.5; không có thì 0.0.
- Bài học: Hit Rate cao chưa đủ, vì tài liệu đúng có thể xuất hiện quá muộn (MRR thấp), làm Generation dễ dùng nhầm context.

### 3.2 Agreement và độ tin cậy Judge
- Điểm Judge cao không đồng nghĩa hệ thống đúng về RAG.
- Cần theo dõi agreement giữa các judge để hạn chế thiên lệch chấm điểm.
- Hướng nâng cao đã đề xuất: dùng Cohen's Kappa để đo mức đồng thuận vượt ra ngoài trùng hợp ngẫu nhiên.

### 3.3 Position Bias trong LLM Judge
- Judge có thể thiên vị đáp án ở vị trí đầu/cuối nếu prompt không kiểm soát tốt.
- Hướng xử lý: đánh giá đảo thứ tự đáp án (A/B swap) để phát hiện position bias trước khi dùng điểm judge cho quyết định release.

### 3.4 Trade-off chi phí và chất lượng
- Nếu tăng số judge model và tăng depth đánh giá, chi phí/tokens tăng đáng kể.
- Giải pháp thực tế:
  - Judge nhẹ cho pre-screen.
  - Chỉ dùng judge mạnh cho các case conflict hoặc score không chắc chắn.

## 4. Problem Solving
- Vấn đề thực tế gặp phải:
  - Tình huống pass 100% theo judge nhưng vẫn có retrieval failure ở một số case khó.
  - Báo cáo ban đầu lệch số lượng case và lệch case ID so với benchmark mới.
- Cách giải quyết:
  - Chạy lại benchmark để tạo report mới.
  - Map lại case theo câu hỏi từ `data/golden_set.jsonl` sang `reports/benchmark_results.json`.
  - Cập nhật lại `failure_analysis.md` với số liệu và case ID đúng thực tế.
- Kết quả:
  - Báo cáo trở nên nhất quán với dữ liệu chạy thật.
  - Rủi ro bị trừ điểm do sai dữ liệu giảm rõ rệt.

## 5. Bài học rút ra
1. Trong hệ thống RAG, phải tách riêng đánh giá Retrieval và Generation.
2. Không nên kết luận chất lượng chỉ từ điểm judge trung bình.
3. Báo cáo kỹ thuật phải bám đúng artifact đầu ra (reports), tránh mô tả theo cảm giác.
4. Hard cases là nguồn thông tin tốt nhất để tối ưu pipeline.

## 6. Kế hoạch cải tiến cá nhân
- [ ] Bổ sung script tự động kiểm tra consistency giữa `golden_set` và `benchmark_results`.
- [ ] Thử nghiệm Hybrid Retrieval (Dense + BM25) cho các truy vấn có keyword cứng như `P1`, hotline, project code.
- [ ] Đề xuất tích hợp đo Cohen's Kappa và kiểm tra Position Bias vào pipeline judge.
- [ ] Thiết kế dashboard nhỏ để theo dõi đồng thời Hit Rate, MRR, Judge Score theo từng nhóm hard case.
