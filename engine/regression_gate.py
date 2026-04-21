"""
Regression Gate Module – Quyết định APPROVE / BLOCK release dựa trên ngưỡng.

Thiết kế theo nguyên lý "fail-fast": nếu bất kỳ metric nào vi phạm ngưỡng tối
thiểu thì block ngay; nếu tất cả đều vượt ngưỡng thì approve.

Author: Member 4 – Runner/Performance/Regression Engineer
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Cấu hình ngưỡng mặc định (có thể override khi khởi tạo)
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS = {
    # Quality
    "min_avg_score": 3.0,           # Điểm trung bình judge tối thiểu (1-5)
    "min_pass_rate": 0.60,          # Tỉ lệ pass tối thiểu (60 %)
    "min_agreement_rate": 0.60,     # Đồng thuận judge tối thiểu

    # Retrieval
    "min_hit_rate": 0.50,           # Hit-rate tối thiểu
    "min_mrr": 0.30,                # MRR tối thiểu

    # Performance
    "max_avg_latency_s": 5.0,       # Latency trung bình tối đa (giây)
    "max_p95_latency_s": 10.0,      # P95 latency tối đa (giây)

    # Regression (delta V2-V1)
    "max_score_regression": -0.3,   # Cho phép giảm tối đa 0.3 điểm
    "max_hit_rate_regression": -0.1,# Cho phép giảm hit-rate tối đa 10 %
    "max_cost_increase_pct": 50.0,  # Chi phí tăng tối đa 50 %
}


@dataclass
class GateCheck:
    """Một mục kiểm tra trong release gate."""
    name: str
    metric_name: str
    threshold: float
    actual: float
    passed: bool
    direction: str = "min"  # min = actual >= threshold, max = actual <= threshold

    @property
    def delta(self) -> float:
        return round(self.actual - self.threshold, 4)


@dataclass
class GateResult:
    """Kết quả tổng hợp release gate."""
    decision: str                       # "APPROVE" | "BLOCK"
    timestamp: str = ""
    checks: List[GateCheck] = field(default_factory=list)
    passed_checks: int = 0
    failed_checks: int = 0
    total_checks: int = 0
    regression_delta: Dict[str, float] = field(default_factory=dict)
    summary_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


class RegressionGate:
    """
    Đánh giá kết quả benchmark theo ngưỡng cấu hình.

    Sử dụng:
        gate = RegressionGate()
        result = gate.evaluate(v2_summary, v1_summary)
        print(result.decision)  # "APPROVE" hoặc "BLOCK"
    """

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def evaluate(
        self,
        current_summary: Dict[str, Any],
        baseline_summary: Optional[Dict[str, Any]] = None,
    ) -> GateResult:
        """
        Đánh giá current_summary (V2) so với baseline_summary (V1).
        Trả về GateResult với decision APPROVE / BLOCK.
        """
        checks: List[GateCheck] = []
        metrics = current_summary.get("metrics", {})
        perf = current_summary.get("performance", {})

        # --- Quality checks ---
        checks.append(self._check_min("avg_score", metrics.get("avg_score", 0), self.thresholds["min_avg_score"]))
        checks.append(self._check_min("pass_rate", metrics.get("pass_rate", 0), self.thresholds["min_pass_rate"]))
        checks.append(self._check_min("agreement_rate", metrics.get("agreement_rate", 0), self.thresholds["min_agreement_rate"]))

        # --- Retrieval checks ---
        checks.append(self._check_min("hit_rate", metrics.get("hit_rate", 0), self.thresholds["min_hit_rate"]))
        checks.append(self._check_min("mrr", metrics.get("mrr", 0), self.thresholds["min_mrr"]))

        # --- Performance checks ---
        checks.append(self._check_max("avg_latency_s", perf.get("avg_latency_s", 0), self.thresholds["max_avg_latency_s"]))
        checks.append(self._check_max("p95_latency_s", perf.get("p95_latency_s", 0), self.thresholds["max_p95_latency_s"]))

        # --- Regression checks (nếu có baseline) ---
        regression_delta: Dict[str, float] = {}
        if baseline_summary:
            bl_metrics = baseline_summary.get("metrics", {})

            score_delta = metrics.get("avg_score", 0) - bl_metrics.get("avg_score", 0)
            regression_delta["avg_score_delta"] = round(score_delta, 4)
            checks.append(self._check_min(
                "score_regression", score_delta, self.thresholds["max_score_regression"],
            ))

            hr_delta = metrics.get("hit_rate", 0) - bl_metrics.get("hit_rate", 0)
            regression_delta["hit_rate_delta"] = round(hr_delta, 4)
            checks.append(self._check_min(
                "hit_rate_regression", hr_delta, self.thresholds["max_hit_rate_regression"],
            ))

            # Cost increase percentage
            bl_cost = baseline_summary.get("cost", {}).get("total_estimated_cost_usd", 0)
            cur_cost = current_summary.get("cost", {}).get("total_estimated_cost_usd", 0)
            if bl_cost > 0:
                cost_pct = ((cur_cost - bl_cost) / bl_cost) * 100
            else:
                cost_pct = 0.0
            regression_delta["cost_increase_pct"] = round(cost_pct, 2)
            checks.append(self._check_max(
                "cost_increase_pct", cost_pct, self.thresholds["max_cost_increase_pct"],
            ))

        # --- Aggregate ---
        passed = sum(1 for c in checks if c.passed)
        failed = sum(1 for c in checks if not c.passed)
        decision = "APPROVE" if failed == 0 else "BLOCK"

        result = GateResult(
            decision=decision,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            checks=checks,
            passed_checks=passed,
            failed_checks=failed,
            total_checks=len(checks),
            regression_delta=regression_delta,
            summary_text=self._summary_text(decision, checks),
        )
        return result

    def save_gate_report(self, result: GateResult, path: str = "reports/gate_report.json") -> None:
        """Lưu kết quả gate ra file JSON."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _check_min(self, name: str, actual: float, threshold: float) -> GateCheck:
        return GateCheck(
            name=name,
            metric_name=name,
            threshold=threshold,
            actual=round(actual, 4),
            passed=actual >= threshold,
            direction="min",
        )

    def _check_max(self, name: str, actual: float, threshold: float) -> GateCheck:
        return GateCheck(
            name=name,
            metric_name=name,
            threshold=threshold,
            actual=round(actual, 4),
            passed=actual <= threshold,
            direction="max",
        )

    def _summary_text(self, decision: str, checks: List[GateCheck]) -> str:
        lines = [f"Release Gate Decision: {decision}"]
        for c in checks:
            icon = "✅" if c.passed else "❌"
            direction_label = ">=" if c.direction == "min" else "<="
            lines.append(
                f"  {icon} {c.name}: {c.actual:.4f} {direction_label} {c.threshold:.4f}"
            )
        return "\n".join(lines)
