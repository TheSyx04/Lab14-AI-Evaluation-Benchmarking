"""
Benchmark Runner – Async pipeline cho toàn bộ golden dataset.

Tính năng chính (Member 4 deliverables):
  • Async batching với semaphore để tránh rate-limit.
  • Thu thập latency, token usage, cost estimate cho mỗi case.
  • Tổng hợp performance metrics:  avg / p50 / p95 / max latency.
  • Tích hợp RegressionGate để tự động APPROVE/BLOCK release.
  • Sinh reports/summary.json + reports/benchmark_results.json.

KHÔNG thay đổi main.py – module này mở rộng tính năng trong nội bộ
engine/ và trả về kết quả tương thích với API cũ.

Author: Member 4 – Runner/Performance/Regression Engineer
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from typing import Any, Dict, List, Optional

from engine.retrieval_eval import RetrievalEvaluator
from engine.regression_gate import RegressionGate, GateResult


# ---------------------------------------------------------------------------
# Cost estimation constants (USD per 1K tokens – approximate GPT-4o pricing)
# ---------------------------------------------------------------------------
COST_PER_1K_INPUT_TOKENS = 0.0025     # $2.50 / 1M input tokens
COST_PER_1K_OUTPUT_TOKENS = 0.010     # $10.00 / 1M output tokens
DEFAULT_INPUT_TOKENS = 120            # Estimated input tokens per agent call
DEFAULT_OUTPUT_TOKENS = 80            # Estimated output tokens per agent call


class BenchmarkRunner:
    """
    Orchestrator chính cho benchmark pipeline.

    Giữ nguyên chữ ký ``__init__(self, agent, evaluator, judge)`` và
    ``run_all(dataset) -> List[Dict]`` để tương thích main.py.
    """

    def __init__(
        self,
        agent,
        evaluator,
        judge,
        *,
        max_concurrency: int = 10,
        batch_size: int = 5,
        top_k: int = 3,
    ):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        self.retrieval_evaluator = RetrievalEvaluator(top_k=top_k)
        self.regression_gate = RegressionGate()

        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._batch_size = batch_size

        # Accumulators – populated during run
        self._latencies: List[float] = []
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0

    # ------------------------------------------------------------------
    # Helpers: ID extraction & cost
    # ------------------------------------------------------------------
    def _extract_retrieved_ids(self, response: Dict) -> List[str]:
        """Trích xuất retrieved_ids từ response agent (nhiều format)."""
        direct = response.get("retrieved_ids")
        if isinstance(direct, list) and direct:
            return direct

        metadata = response.get("metadata", {})
        sources = metadata.get("sources") if isinstance(metadata, dict) else []
        if isinstance(sources, list):
            return [
                str(src).rsplit("/", 1)[-1].rsplit("\\", 1)[-1].split(".")[0]
                for src in sources
            ]
        return []

    @staticmethod
    def _estimate_tokens(response: Dict) -> Dict[str, int]:
        """
        Ước lượng token usage từ metadata agent hoặc fallback heuristic.
        """
        metadata = response.get("metadata", {})
        if isinstance(metadata, dict):
            input_tokens = int(metadata.get("input_tokens", 0)) or DEFAULT_INPUT_TOKENS
            output_tokens = int(metadata.get("tokens_used", 0)) or DEFAULT_OUTPUT_TOKENS
        else:
            input_tokens = DEFAULT_INPUT_TOKENS
            output_tokens = DEFAULT_OUTPUT_TOKENS
        return {"input_tokens": input_tokens, "output_tokens": output_tokens}

    @staticmethod
    def _estimate_cost(token_info: Dict[str, int]) -> float:
        """Tính cost estimate (USD) từ token counts."""
        input_cost = (token_info["input_tokens"] / 1000) * COST_PER_1K_INPUT_TOKENS
        output_cost = (token_info["output_tokens"] / 1000) * COST_PER_1K_OUTPUT_TOKENS
        return round(input_cost + output_cost, 6)

    # ------------------------------------------------------------------
    # Single test case
    # ------------------------------------------------------------------
    async def run_single_test(self, test_case: Dict) -> Dict:
        """Chạy 1 test case: Agent → RAGAS → Retrieval → Judge → metrics."""
        async with self._semaphore:
            start_time = time.perf_counter()

            # 1. Gọi Agent
            response = await self.agent.query(test_case["question"])
            latency = time.perf_counter() - start_time
            self._latencies.append(latency)

            retrieved_ids = self._extract_retrieved_ids(response)

            # 2. Token & cost estimation
            token_info = self._estimate_tokens(response)
            self._total_input_tokens += token_info["input_tokens"]
            self._total_output_tokens += token_info["output_tokens"]
            cost = self._estimate_cost(token_info)

            # 3. RAGAS metrics (evaluator)
            ragas_scores = await self.evaluator.score(test_case, response)
            ragas_scores["retrieval"] = {
                "hit_rate": self.retrieval_evaluator.calculate_hit_rate(
                    test_case.get("expected_retrieval_ids", []),
                    retrieved_ids,
                ),
                "mrr": self.retrieval_evaluator.calculate_mrr(
                    test_case.get("expected_retrieval_ids", []),
                    retrieved_ids,
                ),
                "expected_retrieval_ids": test_case.get("expected_retrieval_ids", []),
                "retrieved_ids": retrieved_ids,
            }

            # 4. Multi-Judge
            judge_result = await self.judge.evaluate_multi_judge(
                test_case["question"],
                response["answer"],
                test_case["expected_answer"],
            )

            # 5. Determine pass/fail
            status = "pass" if judge_result["final_score"] >= 3 else "fail"

            return {
                "test_case": test_case["question"],
                "expected_answer": test_case.get("expected_answer", ""),
                "agent_response": response["answer"],
                "latency": round(latency, 4),
                "tokens": token_info,
                "cost_usd": cost,
                "ragas": ragas_scores,
                "judge": judge_result,
                "status": status,
                "metadata": {
                    "difficulty": test_case.get("metadata", {}).get("difficulty", "unknown"),
                    "type": test_case.get("metadata", {}).get("type", "unknown"),
                },
            }

    # ------------------------------------------------------------------
    # Run all
    # ------------------------------------------------------------------
    async def run_all(self, dataset: List[Dict], batch_size: int = 5) -> List[Dict]:
        """
        Chạy song song bằng asyncio.gather với giới hạn batch_size
        để không bị Rate Limit.

        Trả về list results tương thích với main.py.
        """
        effective_batch = batch_size or self._batch_size
        self._latencies = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        results: List[Dict] = []
        total = len(dataset)

        for i in range(0, total, effective_batch):
            batch = dataset[i : i + effective_batch]
            batch_num = (i // effective_batch) + 1
            total_batches = (total + effective_batch - 1) // effective_batch
            print(f"  ⏳ Batch {batch_num}/{total_batches} ({len(batch)} cases)...")

            tasks = [self.run_single_test(case) for case in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

        # Attach retrieval mapping report (first 10 cases) – member-2 deliverable
        mapping_dataset = [
            {
                "id": f"case_{idx + 1:03d}",
                "expected_retrieval_ids": r.get("ragas", {}).get("retrieval", {}).get("expected_retrieval_ids", []),
                "retrieved_ids": r.get("ragas", {}).get("retrieval", {}).get("retrieved_ids", []),
            }
            for idx, r in enumerate(results)
        ]
        retrieval_summary = await self.retrieval_evaluator.evaluate_batch(mapping_dataset)
        for idx, row in enumerate(results):
            if idx < len(retrieval_summary["sample_mapping_report"]):
                row["retrieval_mapping_check"] = retrieval_summary["sample_mapping_report"][idx]

        return results

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------
    def build_summary(
        self,
        results: List[Dict],
        agent_version: str = "Agent_V2_Optimized",
    ) -> Dict[str, Any]:
        """
        Tạo summary dict (tương thích main.py) VỚI thêm performance & cost.
        """
        total = len(results)
        if total == 0:
            return {"metadata": {"version": agent_version, "total": 0}, "metrics": {}}

        latencies = [r["latency"] for r in results]
        sorted_lat = sorted(latencies)

        pass_count = sum(1 for r in results if r["status"] == "pass")
        fail_count = total - pass_count

        summary = {
            "metadata": {
                "version": agent_version,
                "total": total,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "pass_count": pass_count,
                "fail_count": fail_count,
            },
            "metrics": {
                "avg_score": round(
                    sum(r["judge"]["final_score"] for r in results) / total, 4
                ),
                "pass_rate": round(pass_count / total, 4),
                "hit_rate": round(
                    sum(r["ragas"]["retrieval"]["hit_rate"] for r in results) / total, 4
                ),
                "mrr": round(
                    sum(r["ragas"]["retrieval"]["mrr"] for r in results) / total, 4
                ),
                "agreement_rate": round(
                    sum(r["judge"]["agreement_rate"] for r in results) / total, 4
                ),
            },
            "performance": {
                "total_time_s": round(sum(latencies), 4),
                "avg_latency_s": round(statistics.mean(latencies), 4),
                "median_latency_s": round(statistics.median(latencies), 4),
                "p95_latency_s": round(self._percentile(sorted_lat, 95), 4),
                "max_latency_s": round(max(latencies), 4),
                "min_latency_s": round(min(latencies), 4),
                "stddev_latency_s": round(
                    statistics.stdev(latencies) if len(latencies) > 1 else 0.0, 4
                ),
            },
            "cost": {
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_tokens": self._total_input_tokens + self._total_output_tokens,
                "total_estimated_cost_usd": round(
                    sum(r.get("cost_usd", 0) for r in results), 6
                ),
                "avg_cost_per_case_usd": round(
                    sum(r.get("cost_usd", 0) for r in results) / total, 6
                ),
                "cost_model": "gpt-4o-estimate",
            },
        }
        return summary

    # ------------------------------------------------------------------
    # Regression analysis
    # ------------------------------------------------------------------
    def run_regression(
        self,
        v2_summary: Dict[str, Any],
        v1_summary: Optional[Dict[str, Any]] = None,
    ) -> GateResult:
        """Chạy regression gate và trả về GateResult."""
        return self.regression_gate.evaluate(v2_summary, v1_summary)

    def print_regression_report(
        self,
        gate_result: GateResult,
        v1_summary: Optional[Dict[str, Any]] = None,
        v2_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """In báo cáo regression đẹp ra console."""
        print("\n" + "=" * 60)
        print("📊 REGRESSION GATE REPORT")
        print("=" * 60)

        if v1_summary and v2_summary:
            v1m = v1_summary.get("metrics", {})
            v2m = v2_summary.get("metrics", {})
            print(f"\n  V1 Avg Score: {v1m.get('avg_score', 'N/A')}")
            print(f"  V2 Avg Score: {v2m.get('avg_score', 'N/A')}")
            delta = v2m.get("avg_score", 0) - v1m.get("avg_score", 0)
            print(f"  Delta:        {'+' if delta >= 0 else ''}{delta:.4f}")

        print(f"\n  Checks: {gate_result.passed_checks} passed / "
              f"{gate_result.failed_checks} failed / {gate_result.total_checks} total")

        for check in gate_result.checks:
            icon = "✅" if check.passed else "❌"
            direction_label = ">=" if check.direction == "min" else "<="
            print(f"    {icon} {check.name}: {check.actual:.4f} {direction_label} {check.threshold:.4f}")

        decision_icon = "✅" if gate_result.decision == "APPROVE" else "❌"
        print(f"\n  {decision_icon} QUYẾT ĐỊNH: {gate_result.decision}")
        print("=" * 60)

    # ------------------------------------------------------------------
    # Report persistence
    # ------------------------------------------------------------------
    def save_reports(
        self,
        results: List[Dict],
        summary: Dict[str, Any],
        gate_result: Optional[GateResult] = None,
        reports_dir: str = "reports",
    ) -> None:
        """Lưu summary.json, benchmark_results.json, và gate_report.json."""
        os.makedirs(reports_dir, exist_ok=True)

        summary_path = os.path.join(reports_dir, "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"  📄 Saved {summary_path}")

        results_path = os.path.join(reports_dir, "benchmark_results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"  📄 Saved {results_path}")

        if gate_result:
            gate_path = os.path.join(reports_dir, "gate_report.json")
            self.regression_gate.save_gate_report(gate_result, gate_path)
            print(f"  📄 Saved {gate_path}")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    @staticmethod
    def _percentile(sorted_list: List[float], pct: int) -> float:
        """Tính percentile từ sorted list."""
        if not sorted_list:
            return 0.0
        k = (len(sorted_list) - 1) * (pct / 100)
        f = int(k)
        c = f + 1
        if c >= len(sorted_list):
            return sorted_list[-1]
        return sorted_list[f] + (k - f) * (sorted_list[c] - sorted_list[f])
