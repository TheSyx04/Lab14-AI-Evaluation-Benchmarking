import asyncio
import time
from typing import List, Dict
from engine.retrieval_eval import RetrievalEvaluator
# Import other components...

class BenchmarkRunner:
    def __init__(self, agent, evaluator, judge):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        self.retrieval_evaluator = RetrievalEvaluator(top_k=3)

    def _extract_retrieved_ids(self, response: Dict) -> List[str]:
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

    async def run_single_test(self, test_case: Dict) -> Dict:
        start_time = time.perf_counter()
        
        # 1. Gọi Agent
        response = await self.agent.query(test_case["question"])
        latency = time.perf_counter() - start_time
        retrieved_ids = self._extract_retrieved_ids(response)
        
        # 2. Chạy RAGAS metrics
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
        
        # 3. Chạy Multi-Judge
        judge_result = await self.judge.evaluate_multi_judge(
            test_case["question"], 
            response["answer"], 
            test_case["expected_answer"]
        )
        
        return {
            "test_case": test_case["question"],
            "agent_response": response["answer"],
            "latency": latency,
            "ragas": ragas_scores,
            "judge": judge_result,
            "status": "fail" if judge_result["final_score"] < 3 else "pass"
        }

    async def run_all(self, dataset: List[Dict], batch_size: int = 5) -> List[Dict]:
        """
        Chạy song song bằng asyncio.gather với giới hạn batch_size để không bị Rate Limit.
        """
        results = []
        for i in range(0, len(dataset), batch_size):
            batch = dataset[i:i + batch_size]
            tasks = [self.run_single_test(case) for case in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

        # Attach a lightweight ID mapping report (first 10 cases) for member-2 deliverable.
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
