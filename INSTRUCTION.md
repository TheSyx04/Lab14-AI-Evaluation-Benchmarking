# INSTRUCTION - Kế hoạch thực thi Lab Day 14 (Team 5 người)

## 1) Mục tiêu hôm nay
- Hoàn thiện Evaluation Factory đủ điều kiện chấm Expert Level.
- Chạy benchmark end-to-end với tối thiểu 50 test cases.
- Có báo cáo định lượng rõ: chất lượng, retrieval, đồng thuận judge, hiệu năng, chi phí.
- Có phân tích thất bại sâu (Failure Clustering + 5 Whys) và kế hoạch cải tiến.

## 0) Ràng buộc bắt buộc
- KHÔNG thay đổi file main.py trong bất kỳ task nào hôm nay. Mọi cải tiến phải thực hiện ở các module khác (engine/, agent/, data/, analysis/).

## 2) Công việc phải làm trong hôm nay

### A. Data + SDG (bắt buộc)
- Nâng cấp data/synthetic_gen.py để sinh tối thiểu 50 test cases vào data/golden_set.jsonl.
- Mỗi case cần có tối thiểu các trường:
  - question
  - expected_answer
  - expected_retrieval_ids (phục vụ Hit Rate/MRR)
  - metadata (difficulty, type)
- Dùng bộ tài liệu hiện có trong data/ để build hoặc tái sử dụng Vector DB từ lab trước (không cần build lại nếu mapping ID còn đúng).
- Bổ sung hard cases theo data/HARD_CASES_GUIDE.md:
  - adversarial/prompt injection
  - out-of-context
  - ambiguous
  - conflicting information
  - multi-turn hoặc correction

### B. Retrieval Evaluation (bắt buộc)
- Hoàn thiện engine/retrieval_eval.py:
  - calculate_hit_rate
  - calculate_mrr
  - evaluate_batch với dữ liệu thật từ agent output (retrieved_ids).
- Chuẩn hóa ID giữa retriever và golden set:
  - retrieved_ids phải cùng format với expected_retrieval_ids
  - xác minh tối thiểu 10 case đầu có mapping đúng
- Tích hợp retrieval metrics vào pipeline để summary có:
  - hit_rate
  - mrr (khuyến nghị thêm vào summary)

### C. Multi-Judge Consensus (bắt buộc)
- Hoàn thiện engine/llm_judge.py:
  - dùng >= 2 judge model (ví dụ OpenAI + Anthropic)
  - trả về điểm từng judge + final_score + agreement_rate
  - có logic xử lý khi chênh lệch điểm lớn (xung đột)
- Viết rubric rõ ràng cho accuracy/professionalism/safety.

### D. Benchmark Runner + Regression Gate (bắt buộc)
- Hoàn thiện engine/runner.py và các module liên quan (không sửa main.py) để:
  - chạy async ổn định cho toàn bộ dataset
  - thu thập latency, token usage, cost estimate
  - so sánh V1 vs V2 (delta analysis)
  - đưa ra quyết định release gate (APPROVE/BLOCK) theo ngưỡng rõ ràng
- Bảo đảm tạo được:
  - reports/summary.json
  - reports/benchmark_results.json

### E. Failure Analysis + Báo cáo (bắt buộc)
- Điền đầy đủ analysis/failure_analysis.md:
  - pass/fail, điểm trung bình
  - failure clustering
  - 5 whys cho 3 case tệ nhất
  - action plan cải tiến
- Tạo thư mục analysis/reflections và 5 file reflection cá nhân:
  - analysis/reflections/reflection_member1.md
  - analysis/reflections/reflection_member2.md
  - analysis/reflections/reflection_member3.md
  - analysis/reflections/reflection_member4.md
  - analysis/reflections/reflection_member5.md

### F. Kiểm tra trước khi nộp
- Chạy theo thứ tự:
  1. pip install -r requirements.txt
  2. python data/synthetic_gen.py
  3. python main.py
  4. python check_lab.py
- Không push file .env.

## 3) Các thứ cần nộp
- 01 link repository chứa:
  - Source code hoàn chỉnh.
  - reports/summary.json.
  - reports/benchmark_results.json.
  - analysis/failure_analysis.md đã điền đầy đủ.
  - analysis/reflections/reflection_[Tên_thành_viên].md cho tất cả thành viên.
- Khuyến nghị đính kèm trong README hoặc note nội bộ:
  - kết quả regression V1 vs V2
  - cách tái chạy benchmark
  - giải thích ngưỡng release gate

## 4) Phân chia công việc cho 5 thành viên

## Thành viên 1 - Data/SDG Lead
- Phụ trách:
  - data/synthetic_gen.py
  - chuẩn bị nguồn dữ liệu từ 5 file policy hiện tại trong data/
  - build/tái sử dụng Vector DB từ lab trước (ưu tiên tái sử dụng)
  - chuẩn schema golden_set.jsonl
  - hard cases coverage >= 20% dataset
- Deliverables cuối ngày:
  - script sinh >= 50 cases chạy ổn định
  - danh sách tài liệu đã index + thống nhất quy ước chunk/doc ID
  - thống kê phân bố difficulty/type
  - PR: feat(data): generate golden set with hard cases and retrieval ids

## Thành viên 2 - Retrieval Metrics Engineer
- Phụ trách:
  - engine/retrieval_eval.py
  - tích hợp retriever với Vector DB (hoặc adapter đọc từ retriever hiện có)
  - tích hợp expected_retrieval_ids và retrieved_ids
- Deliverables cuối ngày:
  - hàm evaluate_batch chạy thật, không placeholder
  - báo cáo kiểm tra mapping ID (expected vs retrieved) cho sample cases
  - metrics hit_rate và mrr xuất được vào summary/results
  - PR: feat(eval): retrieval metrics hit rate mrr integration

## Thành viên 3 - Multi-Judge Engineer
- Phụ trách:
  - engine/llm_judge.py
  - consensus, agreement, conflict handling
- Deliverables cuối ngày:
  - gọi được >= 2 judge models
  - rubric rõ ràng + output JSON nhất quán
  - PR: feat(judge): multi model consensus and disagreement handling

## Thành viên 4 - Runner/Performance/Regression Engineer
- Phụ trách:
  - engine/runner.py
  - phối hợp module để giữ pipeline chạy qua entrypoint hiện tại mà không chỉnh main.py
  - benchmark async + cost/latency + release gate
- Deliverables cuối ngày:
  - pipeline chạy < 2 phút cho 50 cases (mục tiêu)
  - reports/summary.json + reports/benchmark_results.json sinh đúng
  - PR: feat(runner): async benchmark and regression gate

## Thành viên 5 - QA/Analysis/Submission Owner
- Phụ trách:
  - analysis/failure_analysis.md
  - analysis/reflections/*
  - check_lab.py validation + checklist nộp bài
- Deliverables cuối ngày:
  - failure analysis đầy đủ (clustering + 5 whys + action plan)
  - tổng hợp reflection 5 người
  - chạy check_lab.py pass
  - PR: docs(analysis): failure report, reflections, final submission checklist

## 5) Timeline gợi ý (4 giờ)
- 00:00-00:45
  - Member 1 làm dataset
  - Member 2 chốt schema retrieval ids
  - Member 3 viết rubric judge
  - Member 4 chuẩn runner async skeleton
  - Member 5 chuẩn template analysis/reflection
- 00:45-02:15
  - Member 2,3,4 triển khai core engine
  - Member 1 bổ sung hard cases + validate dữ liệu
  - Member 5 theo dõi test log, ghi nhận lỗi
- 02:15-03:15
  - chạy benchmark lần 1
  - phân tích lỗi, tối ưu nhanh
  - chạy benchmark lần 2 và regression
- 03:15-04:00
  - hoàn thiện analysis + reflections
  - check_lab.py
  - chốt checklist nộp và merge nhánh

## 6) Definition of Done (DoD)
- Có >= 50 cases trong golden_set.jsonl (sinh từ script).
- Có retrieval metrics (hit_rate, mrr) trong kết quả.
- Có multi-judge thật với agreement_rate và xử lý xung đột.
- Có reports/summary.json và reports/benchmark_results.json sau khi chạy main.py.
- Có failure_analysis.md đầy đủ + 5 reflection cá nhân.
- check_lab.py chạy không báo thiếu file.

## 7) Checklist nghiệm thu theo thành viên (tick khi hoàn tất)

### Member 1 - Data + Vector DB
- [x] Đã xác nhận 5 tài liệu nguồn trong data/ được đưa vào index.
- [x] Đã build/tái sử dụng Vector DB thành công.
- [x] Đã chốt quy ước ID (doc_id/chunk_id) và chia sẻ cho team.
- [x] Đã sinh data/golden_set.jsonl với >= 50 cases.
- [x] Hard cases >= 20% tổng số cases.

### Member 2 - Retrieval Metrics
- [ ] retriever trả về retrieved_ids đúng format đã thống nhất.
- [ ] expected_retrieval_ids trong golden set map đúng với retrieved_ids.
- [ ] calculate_hit_rate hoạt động đúng với test sample.
- [ ] calculate_mrr hoạt động đúng với test sample.
- [ ] evaluate_batch không còn placeholder.

### Member 3 - Multi-Judge
- [ ] Có ít nhất 2 judge model trong pipeline.
- [ ] Có rubric rõ ràng cho accuracy/professionalism/safety.
- [ ] Có agreement_rate và individual_scores.
- [ ] Có logic xử lý khi chênh lệch điểm lớn.
- [ ] Output judge nhất quán JSON schema.

### Member 4 - Runner/Performance
- [ ] Không thay đổi main.py.
- [ ] runner chạy async ổn định cho toàn bộ dataset.
- [ ] Thu thập được latency/token/cost (hoặc cost estimate).
- [ ] Có cơ chế regression gate (APPROVE/BLOCK) theo ngưỡng.
- [ ] Sinh được reports/summary.json và reports/benchmark_results.json.

### Member 5 - QA/Analysis/Submission
- [ ] Điền đầy đủ analysis/failure_analysis.md.
- [ ] Có 3 case 5-Whys cụ thể và action plan.
- [ ] Thu đủ reflection của 5 thành viên.
- [ ] Chạy python check_lab.py và không thiếu file nộp.
- [ ] Soát lần cuối: không commit .env và secrets.

### Final Team Gate (trước khi nộp)
- [ ] Tất cả checklist của 5 member đã tick xong.
- [ ] Benchmark chạy lại 1 lần cuối không lỗi.
- [ ] Reports và analysis đã cập nhật đúng bản chạy cuối.
- [ ] Repo ở trạng thái có thể chấm tự động ngay.
