"""
RAG Pipeline: LangChain chunking + Hybrid retrieval + Gemini streaming.
Tích hợp: Conversation Memory, Prompt Templates, Evaluation Metrics.
"""

import asyncio
import queue
import time
import threading
from typing import AsyncIterator, Optional

import google.generativeai as genai
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import settings
from core.evaluator import ResponseMetrics, Timer, evaluator
from core.hybrid_retriever import retriever
from core.memory import memory_store
from core.prompts import build_rag_prompt, get_prompt

genai.configure(api_key=settings.gemini_api_key)

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    separators=["\n\n", "\n", ".", "!", "?", " ", ""],
)


def index_document(text: str, doc_id: str, filename: str) -> int:
    chunks = _splitter.split_text(text)
    retriever.add_chunks(
        [
            {"text": c, "meta": {"doc_id": doc_id, "filename": filename, "chunk_idx": i}}
            for i, c in enumerate(chunks)
        ]
    )
    return len(chunks)


async def rag_stream(
    query: str,
    session_id: str = "default",
    provider: str = "gemini",
    prompt_name: str = "rag_vi",
) -> AsyncIterator[str]:
    """Stream RAG response với memory + prompt management + evaluation."""
    t_start = time.perf_counter()

    docs = retriever.search(query, k=settings.max_context_docs)

    if not docs:
        yield "⚠️ Chưa có tài liệu nào. Hãy upload tài liệu trước khi đặt câu hỏi."
        return

    context = "\n\n---\n\n".join(
        f"**[{d['meta']['filename']} — Chunk {d['meta']['chunk_idx'] + 1}]**\n{d['text']}"
        for d in docs
    )

    history_ctx = memory_store.as_context_string(session_id)
    prompt = build_rag_prompt(query, context, prompt_name, history_ctx)

    answer_buf = ""
    result_q: queue.Queue = queue.Queue()

    def _run_gemini() -> None:
        try:
            model = genai.GenerativeModel(settings.chat_model)
            for chunk in model.generate_content(prompt, stream=True):
                if chunk.text:
                    result_q.put(chunk.text)
        except Exception as exc:
            result_q.put(f"\n\n⚠️ Lỗi API: {exc}")
        finally:
            result_q.put(None)

    threading.Thread(target=_run_gemini, daemon=True).start()

    loop = asyncio.get_running_loop()
    while True:
        text = await loop.run_in_executor(None, result_q.get)
        if text is None:
            break
        answer_buf += text
        yield text

    # Update memory
    memory_store.add(session_id, "user", query)
    memory_store.add(session_id, "assistant", answer_buf[:500])

    # Log evaluation metrics
    elapsed_ms = round((time.perf_counter() - t_start) * 1000)
    evaluator.log(
        ResponseMetrics(
            session_id=session_id,
            mode="rag",
            provider=provider,
            prompt_name=prompt_name,
            query_len=len(query),
            docs_retrieved=len(docs),
            retrieval_scores=[],
            token_estimate=len(answer_buf) // 4,
            latency_ms=elapsed_ms,
        )
    )
