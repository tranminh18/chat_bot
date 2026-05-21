"""
AI Agent với Gemini Function Calling.
Tool-calling loop: LLM quyết định công cụ → thực thi → trả kết quả → lặp → trả lời cuối.
Yield từng event (tool_call, tool_result, answer_token, metrics) để stream lên frontend.
"""

import asyncio
import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import google.generativeai as genai

from core.config import settings
from core.hybrid_retriever import retriever

genai.configure(api_key=settings.gemini_api_key)

# ── Tool Definitions (Gemini FunctionDeclaration format) ───────────────────

_TOOL_DECLARATIONS = [
    genai.protos.FunctionDeclaration(
        name="search_documents",
        description="Tìm kiếm trong tài liệu đã upload để lấy thông tin liên quan.",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "query": genai.protos.Schema(
                    type=genai.protos.Type.STRING,
                    description="Câu truy vấn tìm kiếm",
                )
            },
            required=["query"],
        ),
    ),
    genai.protos.FunctionDeclaration(
        name="list_documents",
        description="Liệt kê tất cả tài liệu đã upload trong hệ thống.",
        parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={}),
    ),
    genai.protos.FunctionDeclaration(
        name="get_datetime",
        description="Lấy ngày giờ hiện tại.",
        parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={}),
    ),
    genai.protos.FunctionDeclaration(
        name="calculate",
        description="Tính toán biểu thức toán học. Ví dụ: '150 * 0.1 + 50'",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "expression": genai.protos.Schema(
                    type=genai.protos.Type.STRING,
                    description="Biểu thức toán học hợp lệ",
                )
            },
            required=["expression"],
        ),
    ),
]

_TOOLS = [genai.protos.Tool(function_declarations=_TOOL_DECLARATIONS)]

_AGENT_SYSTEM = """Bạn là AI Agent thông minh với khả năng sử dụng công cụ.
Luôn sử dụng công cụ phù hợp khi cần thông tin. Trả lời bằng ngôn ngữ của người dùng.
Dùng markdown khi phù hợp."""


# ── Tool Execution ─────────────────────────────────────────────────────────

def _run_tool(name: str, args: dict) -> str:
    if name == "search_documents":
        query = args.get("query", "")
        docs = retriever.search(query, k=4)
        if not docs:
            return "Không tìm thấy tài liệu nào liên quan."
        parts = [
            f"[{d['meta']['filename']} | Chunk {d['meta']['chunk_idx'] + 1}]\n{d['text']}"
            for d in docs
        ]
        return "\n\n---\n\n".join(parts)

    if name == "list_documents":
        meta_file = Path("data/documents.json")
        if not meta_file.exists():
            return "Chưa có tài liệu nào."
        docs = json.loads(meta_file.read_text(encoding="utf-8"))
        if not docs:
            return "Chưa có tài liệu nào."
        return "\n".join(f"• {d['filename']} ({d['chunks']} chunks, {d['size']//1024}KB)" for d in docs)

    if name == "get_datetime":
        now = datetime.now()
        days = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        return f"{days[now.weekday()]}, {now.strftime('%d/%m/%Y %H:%M:%S')}"

    if name == "calculate":
        expr = args.get("expression", "")
        try:
            safe_builtins = {"abs": abs, "round": round, "min": min, "max": max}
            result = eval(expr, {"__builtins__": safe_builtins})  # noqa: S307
            return f"{expr} = {result}"
        except Exception as exc:
            return f"Lỗi: {exc}"

    return f"Tool '{name}' không tồn tại."


# ── Agent Loop (sync, runs in thread) ─────────────────────────────────────

def _agent_loop(query: str, history: list, result_q: queue.Queue) -> None:
    try:
        t_start = time.perf_counter()
        model = genai.GenerativeModel(
            settings.chat_model,
            system_instruction=_AGENT_SYSTEM,
            tools=_TOOLS,
        )

        # Build chat history (convert to Gemini format)
        chat_history = []
        for msg in history[-6:]:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [{"text": msg["content"]}]})

        chat = model.start_chat(history=chat_history)
        response = chat.send_message(query)

        tool_calls_total = 0
        answer_text = ""

        for _ in range(5):  # max 5 tool-call iterations
            fn_calls = [
                part.function_call
                for part in response.parts
                if hasattr(part, "function_call") and part.function_call.name
            ]

            if not fn_calls:
                # No more tool calls → collect final answer
                for part in response.parts:
                    if hasattr(part, "text") and part.text:
                        answer_text += part.text
                break

            # Execute each tool and emit events
            fn_response_parts = []
            for fc in fn_calls:
                args = {k: v for k, v in fc.args.items()}
                result_q.put({"type": "tool_call", "tool": fc.name, "args": args})
                tool_result = _run_tool(fc.name, args)
                result_q.put({
                    "type": "tool_result",
                    "tool": fc.name,
                    "result": tool_result[:800],
                })
                fn_response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fc.name,
                            response={"result": tool_result},
                        )
                    )
                )
                tool_calls_total += 1

            response = chat.send_message(fn_response_parts)

        # Emit answer (non-streaming for agent mode)
        if answer_text:
            result_q.put({"type": "answer", "content": answer_text})

        elapsed_ms = round((time.perf_counter() - t_start) * 1000)
        result_q.put({
            "type": "metrics",
            "latency_ms": elapsed_ms,
            "token_estimate": len(answer_text) // 4,
            "tool_calls": tool_calls_total,
        })

    except Exception as exc:
        result_q.put({"type": "error", "content": str(exc)})
    finally:
        result_q.put(None)


# ── Async Generator (for FastAPI StreamingResponse) ───────────────────────

async def agent_stream(query: str, history: list = None) -> AsyncIterator[str]:
    result_q: queue.Queue = queue.Queue()
    threading.Thread(
        target=_agent_loop,
        args=(query, history or [], result_q),
        daemon=True,
    ).start()

    loop = asyncio.get_running_loop()
    while True:
        event = await loop.run_in_executor(None, result_q.get)
        if event is None:
            break
        yield json.dumps(event, ensure_ascii=False) + "\n"
