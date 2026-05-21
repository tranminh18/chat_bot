"""
RAG Pipeline: Document chunking (LangChain) + Hybrid retrieval + Gemini streaming generation.
"""

import asyncio
import queue
import threading
from typing import AsyncIterator

import google.generativeai as genai
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import settings
from core.hybrid_retriever import retriever

genai.configure(api_key=settings.gemini_api_key)

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    separators=["\n\n", "\n", ".", "!", "?", "。", " ", ""],
)

_SYSTEM_PROMPT = """Bạn là trợ lý AI thông minh chuyên phân tích và trả lời câu hỏi từ tài liệu.

Quy tắc:
- Trả lời HOÀN TOÀN dựa trên ngữ cảnh tài liệu được cung cấp
- Nếu không tìm thấy thông tin, thành thật nói: "Tài liệu không có thông tin này."
- Trả lời bằng ngôn ngữ của người dùng (Tiếng Việt hoặc English)
- Sử dụng markdown: **bold**, bullet points, bảng khi phù hợp
- Trích dẫn tên file nguồn nếu cần thiết"""


def index_document(text: str, doc_id: str, filename: str) -> int:
    """Split text into chunks and add to vector store."""
    chunks = _splitter.split_text(text)
    retriever.add_chunks(
        [
            {
                "text": chunk,
                "meta": {"doc_id": doc_id, "filename": filename, "chunk_idx": i},
            }
            for i, chunk in enumerate(chunks)
        ]
    )
    return len(chunks)


async def rag_stream(query: str) -> AsyncIterator[str]:
    """Retrieve relevant chunks and stream Gemini response."""
    docs = retriever.search(query, k=settings.max_context_docs)

    if not docs:
        yield "⚠️ Chưa có tài liệu nào trong hệ thống. Hãy upload tài liệu trước khi đặt câu hỏi."
        return

    context_parts = []
    for d in docs:
        meta = d["meta"]
        context_parts.append(
            f"**[{meta['filename']} — Đoạn {meta['chunk_idx'] + 1}]**\n{d['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""{_SYSTEM_PROMPT}

---
**Ngữ cảnh từ tài liệu:**

{context}

---
**Câu hỏi:** {query}

**Trả lời:**"""

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
        yield text
