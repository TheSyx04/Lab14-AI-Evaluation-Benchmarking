from typing import Dict, List, Tuple


class RetrievalEvaluator:
    def __init__(self, top_k: int = 3):
        self.top_k = top_k

    def _normalize_id(self, value: str) -> str:
        return str(value).strip().lower()

    def _normalize_ids(self, ids: List[str]) -> List[str]:
        unique = []
        seen = set()
        for item in ids or []:
            normalized = self._normalize_id(item)
            if normalized and normalized not in seen:
                unique.append(normalized)
                seen.add(normalized)
        return unique

    def _ensure_ids(self, response: Dict, test_case: Dict) -> List[str]:
        # Preferred source: agent response already has normalized retrieval ids.
        candidate = response.get("retrieved_ids")
        if isinstance(candidate, list) and candidate:
            return self._normalize_ids(candidate)

        # Fallback 1: metadata.sources may be doc-level ids.
        metadata = response.get("metadata", {})
        sources = metadata.get("sources") if isinstance(metadata, dict) else None
        if isinstance(sources, list) and sources:
            cleaned = []
            for src in sources:
                raw = str(src).strip()
                stem = raw.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].split(".")[0]
                if stem:
                    cleaned.append(stem)
            return self._normalize_ids(cleaned)

        # Fallback 2: empty list, treated as retrieval miss.
        return []

    def calculate_hit_rate(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = None) -> float:
        k = top_k if top_k is not None else self.top_k
        expected = set(self._normalize_ids(expected_ids))
        top_retrieved = self._normalize_ids(retrieved_ids)[:k]
        hit = any(doc_id in expected for doc_id in top_retrieved)
        return 1.0 if hit else 0.0

    def calculate_mrr(self, expected_ids: List[str], retrieved_ids: List[str]) -> float:
        expected = set(self._normalize_ids(expected_ids))
        for i, doc_id in enumerate(self._normalize_ids(retrieved_ids)):
            if doc_id in expected:
                return 1.0 / (i + 1)
        return 0.0

    def _evaluate_case(self, expected_ids: List[str], retrieved_ids: List[str]) -> Tuple[float, float]:
        hit_rate = self.calculate_hit_rate(expected_ids, retrieved_ids, top_k=self.top_k)
        mrr = self.calculate_mrr(expected_ids, retrieved_ids)
        return hit_rate, mrr

    async def evaluate_batch(self, dataset: List[Dict]) -> Dict:
        """
        Dataset item supports:
        - expected_retrieval_ids: List[str]
        - retrieved_ids: List[str] (direct) OR response.retrieved_ids / response.metadata.sources
        """
        if not dataset:
            return {
                "avg_hit_rate": 0.0,
                "avg_mrr": 0.0,
                "sample_mapping_report": [],
                "evaluated_cases": 0,
            }

        total_hit = 0.0
        total_mrr = 0.0
        mapping_report = []

        for idx, row in enumerate(dataset):
            expected_ids = row.get("expected_retrieval_ids", [])

            if "retrieved_ids" in row:
                retrieved_ids = row.get("retrieved_ids", [])
            else:
                retrieved_ids = self._ensure_ids(
                    response=row.get("response", {}),
                    test_case=row,
                )

            hit_rate, mrr = self._evaluate_case(expected_ids, retrieved_ids)
            total_hit += hit_rate
            total_mrr += mrr

            if idx < 10:
                mapping_report.append(
                    {
                        "case_id": row.get("id", f"idx_{idx}"),
                        "expected_retrieval_ids": self._normalize_ids(expected_ids),
                        "retrieved_ids": self._normalize_ids(retrieved_ids),
                        "hit_rate": hit_rate,
                        "mrr": mrr,
                    }
                )

        count = len(dataset)
        return {
            "avg_hit_rate": total_hit / count,
            "avg_mrr": total_mrr / count,
            "sample_mapping_report": mapping_report,
            "evaluated_cases": count,
        }
