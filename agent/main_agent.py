import asyncio
import json
import math
import os
import re
from collections import Counter
from typing import List, Dict

class MainAgent:
    """
    Đây là Agent mẫu sử dụng kiến trúc RAG đơn giản.
    Sinh viên nên thay thế phần này bằng Agent thực tế đã phát triển ở các buổi trước.
    """
    def __init__(self):
        self.name = "SupportAgent-v1"
        self._vector_db = self._load_vector_db()

    def _load_vector_db(self) -> Dict:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, "data", "vector_db_local.json")
        if not os.path.exists(db_path):
            return {}
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower(), flags=re.UNICODE)

    def _query_sparse_vector(self, question: str) -> Dict[str, float]:
        vocab = self._vector_db.get("vocab", [])
        token_to_idx = {token: idx for idx, token in enumerate(vocab)}
        idf = self._vector_db.get("idf", {})
        tf = Counter(self._tokenize(question))
        max_tf = max(tf.values()) if tf else 1
        sparse = {}
        for token, count in tf.items():
            idx = token_to_idx.get(token)
            if idx is None:
                continue
            idx_str = str(idx)
            sparse[idx_str] = (count / max_tf) * float(idf.get(idx_str, 1.0))
        return sparse

    def _cosine(self, q_vec: Dict[str, float], d_vec: Dict[str, float], d_norm: float) -> float:
        if not q_vec or not d_vec or d_norm <= 0:
            return 0.0
        dot = 0.0
        q_norm_sq = 0.0
        for idx, weight in q_vec.items():
            q_norm_sq += weight * weight
            dot += weight * float(d_vec.get(idx, 0.0))
        q_norm = math.sqrt(q_norm_sq)
        if q_norm == 0:
            return 0.0
        return dot / (q_norm * d_norm)

    def _simple_retrieve(self, question: str) -> List[str]:
        vectors = self._vector_db.get("vectors", [])
        if vectors:
            q_vec = self._query_sparse_vector(question)
            ranked = sorted(
                vectors,
                key=lambda item: self._cosine(q_vec, item.get("vector", {}), float(item.get("norm", 0))),
                reverse=True,
            )
            top = [item.get("chunk_id", "") for item in ranked[:3] if item.get("chunk_id")]
            if top:
                return top
        return ["it_helpdesk_faq#S01"]

    async def query(self, question: str) -> Dict:
        """
        Mô phỏng quy trình RAG:
        1. Retrieval: Tìm kiếm context liên quan.
        2. Generation: Gọi LLM để sinh câu trả lời.
        """
        # Giả lập độ trễ mạng/LLM
        await asyncio.sleep(0.5) 
        
        # Giả lập dữ liệu trả về
        retrieved_ids = self._simple_retrieve(question)
        return {
            "answer": f"Dựa trên tài liệu hệ thống, tôi xin trả lời câu hỏi '{question}' như sau: [Câu trả lời mẫu].",
            "retrieved_ids": retrieved_ids,
            "contexts": [
                "Đoạn văn bản trích dẫn 1 dùng để trả lời...",
                "Đoạn văn bản trích dẫn 2 dùng để trả lời..."
            ],
            "metadata": {
                "model": "gpt-4o-mini",
                "tokens_used": 150,
                "sources": retrieved_ids
            }
        }

if __name__ == "__main__":
    agent = MainAgent()
    async def test():
        resp = await agent.query("Làm thế nào để đổi mật khẩu?")
        print(resp)
    asyncio.run(test())
