# Reflection – Member 4: Runner/Performance/Regression Engineer

## 1. Vai trò & Trách nhiệm
- Phụ trách module `engine/runner.py` – Benchmark Runner chính của pipeline.
- Thiết kế và triển khai `engine/regression_gate.py` – Cơ chế release gate tự động.
- Đảm bảo pipeline chạy async ổn định cho toàn bộ dataset (≥ 50 cases).
- Thu thập metrics: latency, token usage, cost estimate cho mỗi test case.
- Phối hợp với các thành viên khác để đảm bảo main.py không bị thay đổi.

## 2. Công việc đã thực hiện

### 2.1 Nâng cấp `engine/runner.py`
- **Async batching với Semaphore**: Sử dụng `asyncio.Semaphore` thay vì chỉ gather theo batch cố định, cho phép kiểm soát concurrency chặt chẽ hơn, tránh rate-limit API.
- **Per-case metrics**: Mỗi test case được ghi nhận đầy đủ:
  - `latency` (giây, độ chính xác `perf_counter`)
  - `tokens` (input_tokens, output_tokens – lấy từ metadata agent hoặc heuristic fallback)
  - `cost_usd` (ước tính chi phí dựa trên bảng giá GPT-4o)
- **Performance aggregation**: Tổng hợp avg / median / p95 / max / min / stddev latency.
- **Summary builder**: Hàm `build_summary()` tạo summary dict mở rộng với performance + cost.
- **Report persistence**: Hàm `save_reports()` sinh `reports/summary.json`, `reports/benchmark_results.json`, và `reports/gate_report.json`.

### 2.2 Tạo mới `engine/regression_gate.py`
- **Configurable thresholds**: Ngưỡng đánh giá mặc định có thể override khi khởi tạo.
- **Multi-dimensional checks**:
  - Quality: avg_score, pass_rate, agreement_rate
  - Retrieval: hit_rate, mrr
  - Performance: avg_latency, p95_latency
  - Regression: score delta, hit_rate delta, cost increase %
- **Decision logic**: Fail-fast – nếu bất kỳ check nào fail → BLOCK; tất cả pass → APPROVE.
- **Structured output**: `GateResult` dataclass với chi tiết từng check, summary text.

### 2.3 Backward compatibility
- Giữ nguyên chữ ký `__init__(self, agent, evaluator, judge)` và `run_all(dataset) -> List[Dict]`.
- Kết quả trả về tương thích hoàn toàn với main.py – không cần sửa main.py.

## 3. Quyết định kỹ thuật quan trọng

| Quyết định | Lý do |
|------------|-------|
| Semaphore thay vì batch-only | Linh hoạt hơn: batch vẫn dùng để group, semaphore kiểm soát tối đa concurrent tasks |
| Cost estimation heuristic | Không phải lúc nào agent cũng trả về token count chính xác, cần fallback |
| Fail-fast gate | Đảm bảo an toàn: 1 metric vi phạm = block release, tránh ship model kém |
| Ngưỡng bảo thủ | min_avg_score=3.0, min_pass_rate=60% – đủ thực tế cho MVP |

## 4. Khó khăn & Cách giải quyết

### Khó khăn 1: Token count không nhất quán
- Agent trả về `tokens_used` trong metadata nhưng không phân biệt input/output.
- **Giải pháp**: Dùng `tokens_used` làm output estimate, fallback DEFAULT nếu thiếu.

### Khó khăn 2: Latency bị ảnh hưởng bởi async scheduling
- Các task chạy đồng thời nên latency đo được có thể bao gồm wait time.
- **Giải pháp**: Sử dụng `time.perf_counter()` ngay trước/sau agent call (trong semaphore context) để đo chính xác nhất.

### Khó khăn 3: Tương thích ngược với main.py
- main.py đã có sẵn logic tạo summary -> không muốn phá vỡ flow.
- **Giải pháp**: Runner mở rộng kết quả (thêm tokens, cost, metadata) mà không thay đổi structure cũ.

## 5. Bài học rút ra
1. **Separation of Concerns**: Tách regression gate thành module riêng giúp dễ test và cấu hình.
2. **Backward Compatibility**: Khi nâng cấp module trong pipeline đã có, luôn giữ interface cũ hoạt động.
3. **Observability**: Thu thập metrics chi tiết giúp debug và optimize dễ dàng hơn.
4. **Cost awareness**: Trong production AI, chi phí eval có thể lớn hơn chi phí inference – cần tối ưu.

## 6. Đề xuất cải tiến
- [ ] Thêm retry logic với exponential backoff cho API calls.
- [ ] Streaming progress bar (tqdm) cho UX tốt hơn khi chạy benchmark.
- [ ] Cache kết quả intermediate để có thể resume nếu pipeline bị gián đoạn.
- [ ] A/B testing framework: so sánh không chỉ V1 vs V2 mà multiple versions cùng lúc.
- [ ] Đề xuất giảm 30% chi phí eval: dùng judge model nhẹ hơn (GPT-4o-mini) cho pre-screening, chỉ dùng GPT-4o cho các case có conflict.
