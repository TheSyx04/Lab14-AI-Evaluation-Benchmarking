# Báo cáo Bài học cá nhân (Reflection) - Thành viên 5

**Vai trò:** QA, Data Analyst & Submission Owner  
**Phụ trách:** Phân tích lỗi (Failure Analysis), tổng hợp Reflections, rà soát chất lượng (check_lab) và nộp bài.

### 1. Các công việc đã thực hiện
- Đọc và phân tích số liệu từ `reports/summary.json` và `reports/benchmark_results.json`.
- Hoàn thiện `analysis/failure_analysis.md`: Xây dựng phân cụm lỗi (Failure Clustering), áp dụng kỹ thuật "5 Whys" để tìm ra nguyên nhân gốc rễ cho 3 case có điểm Retrieval thấp nhất, và đề xuất Kế hoạch cải tiến (Action Plan) thực tế.
- Chạy kiểm thử tự động với `check_lab.py`, rà soát các tiêu chuẩn bảo mật (ẩn `.env`) và đảm bảo dự án đạt 100% yêu cầu về định dạng trước khi nộp.

### 2. Khó khăn gặp phải
- **Đánh lừa thị giác từ các chỉ số:** Khó khăn lớn nhất là đối mặt với kết quả "ảo". Điểm số LLM Judge tổng trung bình rất cao (4.5/5), khiến tôi ban đầu nghĩ hệ thống đang hoạt động hoàn hảo. Tuy nhiên, khi đào sâu vào từng test case, tôi phát hiện ra ở các câu hỏi khó (Adversarial, Cross-doc), điểm Hit Rate lại bằng 0. Việc bóc tách để chứng minh AI đang bị "Hallucination" (tự bịa câu trả lời hợp lý dù tìm sai tài liệu) đòi hỏi phải đối chiếu chéo rất kỹ lưỡng.

### 3. Bài học rút ra (Lessons Learned)
- **Tầm quan trọng của việc đánh giá độc lập (Decoupled Evaluation):** Không bao giờ được phép gộp chung điểm của Generation (Tạo văn bản) và Retrieval (Tìm kiếm). Nếu chỉ nhìn vào câu trả lời mượt mà của LLM mà bỏ qua Hit Rate/MRR, chúng ta sẽ đưa lên production một hệ thống RAG không đáng tin cậy.
- **Giới hạn của Vector Search thuần túy:** Qua phân tích lỗi, tôi nhận thấy Embedding/Vector Search rất dễ bị đánh lừa bởi các từ ngữ cảm xúc hoặc sai lệch ngữ cảnh (các hard cases). Để hệ thống thực sự "Expert", bắt buộc phải có Hybrid Search (Vector + BM25) và bước Reranking.
- **Vai trò của QA trong AI:** Công việc kiểm thử AI không chỉ là chạy code xem có lỗi (bug/crash) hay không, mà là kiểm tra tính logic, tính minh bạch và độ tin cậy của dữ liệu đầu ra.