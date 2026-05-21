"""
Hybrid Retriever: FAISS (vector similarity) + BM25 (keyword) with weighted score fusion.
Architecture inspired by production RAG systems using Milvus + BM25 hybrid search.
"""

import json
import pickle
import threading
import numpy as np
from pathlib import Path
from typing import List

import faiss
from rank_bm25 import BM25Okapi
import google.generativeai as genai

from core.config import settings

genai.configure(api_key=settings.gemini_api_key)

STORE = Path("data/vector_store")
_lock = threading.Lock()


class HybridRetriever:
    def __init__(self):
        self.chunks: List[dict] = []
        self._index: faiss.IndexFlatIP = None
        self._bm25: BM25Okapi = None
        self._load()

    # ── Embedding ──────────────────────────────────────────────────────────

    def _embed(self, text: str, task: str = "retrieval_document") -> np.ndarray:
        result = genai.embed_content(
            model=settings.embedding_model,
            content=text,
            task_type=task,
        )
        v = np.array(result["embedding"], dtype=np.float32)
        norm = np.linalg.norm(v)
        return v / (norm + 1e-8)

    # ── Indexing ───────────────────────────────────────────────────────────

    def add_chunks(self, new_chunks: List[dict]) -> None:
        with _lock:
            for chunk in new_chunks:
                emb = self._embed(chunk["text"])
                chunk["emb"] = emb.tolist()
                self.chunks.append(chunk)
            self._rebuild_index()
            self._persist()

    def _rebuild_index(self) -> None:
        if not self.chunks:
            self._index = None
            self._bm25 = None
            return
        embs = np.array([c["emb"] for c in self.chunks], dtype=np.float32)
        self._index = faiss.IndexFlatIP(embs.shape[1])
        self._index.add(embs)
        self._bm25 = BM25Okapi([c["text"].lower().split() for c in self.chunks])

    # ── Search ─────────────────────────────────────────────────────────────

    def search(self, query: str, k: int = 6) -> List[dict]:
        with _lock:
            if not self.chunks or self._index is None:
                return []
            k = min(k, len(self.chunks))

            # Semantic search via FAISS
            q_emb = self._embed(query, task="retrieval_query").reshape(1, -1)
            D, I = self._index.search(q_emb, k)
            sem_scores = {int(i): float(d) for i, d in zip(I[0], D[0]) if i >= 0}

            # Keyword search via BM25
            tokens = query.lower().split()
            bm25_raw = self._bm25.get_scores(tokens)
            top_idxs = np.argsort(bm25_raw)[::-1][:k]
            max_b = max(float(bm25_raw[top_idxs[0]]), 1e-8)
            bm25_scores = {
                int(i): float(bm25_raw[i]) / max_b
                for i in top_idxs
                if bm25_raw[i] > 0
            }

            # Weighted fusion: 60% semantic + 40% keyword
            all_ids = set(sem_scores) | set(bm25_scores)
            fused = {
                i: sem_scores.get(i, 0.0) * 0.6 + bm25_scores.get(i, 0.0) * 0.4
                for i in all_ids
            }
            ranked = sorted(fused, key=fused.__getitem__, reverse=True)[:k]
            return [self.chunks[i] for i in ranked]

    # ── Deletion ───────────────────────────────────────────────────────────

    def delete_document(self, doc_id: str) -> None:
        with _lock:
            self.chunks = [c for c in self.chunks if c["meta"].get("doc_id") != doc_id]
            self._rebuild_index()
            self._persist()

    # ── Persistence ────────────────────────────────────────────────────────

    def _persist(self) -> None:
        STORE.mkdir(parents=True, exist_ok=True)
        (STORE / "chunks.json").write_text(
            json.dumps(self.chunks, ensure_ascii=False), encoding="utf-8"
        )
        if self._index is not None:
            faiss.write_index(self._index, str(STORE / "faiss.index"))
        if self._bm25 is not None:
            (STORE / "bm25.pkl").write_bytes(pickle.dumps(self._bm25))

    def _load(self) -> None:
        chunks_file = STORE / "chunks.json"
        if chunks_file.exists():
            self.chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
        if self.chunks:
            self._rebuild_index()


retriever = HybridRetriever()
