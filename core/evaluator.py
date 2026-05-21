"""
Model Evaluation & Metrics Logging.
Theo dõi: latency, token estimate, retrieval quality, session stats.
Production: ghi vào PostgreSQL hoặc ClickHouse.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock
from typing import List, Optional

EVAL_LOG = Path("data/eval_log.jsonl")
_lock = Lock()


@dataclass
class ResponseMetrics:
    session_id: str
    mode: str                   # "rag" | "agent"
    provider: str               # "gemini" | "openai" | "anthropic"
    prompt_name: str
    query_len: int
    docs_retrieved: int
    retrieval_scores: List[float]
    token_estimate: int         # chars / 4
    latency_ms: int
    timestamp: float = field(default_factory=time.time)

    @property
    def avg_retrieval_score(self) -> float:
        if not self.retrieval_scores:
            return 0.0
        return round(sum(self.retrieval_scores) / len(self.retrieval_scores), 3)


class Evaluator:
    def __init__(self):
        EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)

    def log(self, metrics: ResponseMetrics) -> None:
        record = asdict(metrics)
        record["avg_retrieval_score"] = metrics.avg_retrieval_score
        with _lock:
            with EVAL_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_session_stats(self, session_id: str) -> dict:
        records = self._read_session(session_id)
        if not records:
            return {"total_queries": 0}
        latencies = [r["latency_ms"] for r in records]
        tokens = [r["token_estimate"] for r in records]
        return {
            "total_queries": len(records),
            "avg_latency_ms": round(sum(latencies) / len(latencies)),
            "avg_tokens": round(sum(tokens) / len(tokens)),
            "providers_used": list({r["provider"] for r in records}),
        }

    def get_global_stats(self) -> dict:
        if not EVAL_LOG.exists():
            return {"total_queries": 0}
        records = []
        with EVAL_LOG.open(encoding="utf-8") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        if not records:
            return {"total_queries": 0}
        latencies = [r["latency_ms"] for r in records]
        return {
            "total_queries": len(records),
            "avg_latency_ms": round(sum(latencies) / len(latencies)),
            "providers_used": dict.fromkeys(r["provider"] for r in records),
        }

    def _read_session(self, session_id: str) -> list:
        if not EVAL_LOG.exists():
            return []
        out = []
        with EVAL_LOG.open(encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("session_id") == session_id:
                        out.append(r)
                except json.JSONDecodeError:
                    pass
        return out


# Global evaluator
evaluator = Evaluator()


# ── Context manager for timing ────────────────────────────────────────────

class Timer:
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000)
