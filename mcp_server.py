"""
MCP (Model Context Protocol) Server – HTTP/JSON-RPC implementation.
Kết nối LLM với tài liệu nội bộ và công cụ thông qua giao thức chuẩn MCP.

Spec: https://modelcontextprotocol.io/specification
Transport: Streamable HTTP (thay vì stdio mặc định)
Endpoints: POST /mcp  →  JSON-RPC 2.0
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.hybrid_retriever import retriever

router = APIRouter()

_META_FILE = Path("data/documents.json")

SERVER_INFO = {
    "name": "document-intelligence-mcp",
    "version": "1.0.0",
    "description": "MCP server exposing document store and search tools",
}


# ── JSON-RPC helpers ───────────────────────────────────────────────────────

def _ok(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


# ── MCP Method Handlers ────────────────────────────────────────────────────

def _handle_initialize(params: dict) -> dict:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False},
        },
        "serverInfo": SERVER_INFO,
    }


def _handle_tools_list(_: dict) -> dict:
    return {
        "tools": [
            {
                "name": "search_documents",
                "description": "Tìm kiếm ngữ nghĩa + từ khoá (Hybrid: FAISS + BM25) trong tài liệu đã index.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Câu truy vấn"},
                        "top_k": {"type": "integer", "default": 4, "description": "Số kết quả tối đa"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "list_documents",
                "description": "Liệt kê tất cả tài liệu đã upload và được index.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_server_info",
                "description": "Lấy thông tin server MCP và trạng thái hiện tại.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
    }


def _handle_tools_call(params: dict) -> dict:
    name = params.get("name", "")
    args = params.get("arguments", {})

    if name == "search_documents":
        query = args.get("query", "")
        top_k = int(args.get("top_k", 4))
        docs = retriever.search(query, k=top_k)
        if not docs:
            content = "Không tìm thấy kết quả phù hợp."
        else:
            parts = [
                f"[{d['meta']['filename']} | Chunk {d['meta']['chunk_idx'] + 1}]\n{d['text']}"
                for d in docs
            ]
            content = "\n\n---\n\n".join(parts)
        return {"content": [{"type": "text", "text": content}], "isError": False}

    if name == "list_documents":
        if not _META_FILE.exists():
            text = "Chưa có tài liệu nào."
        else:
            docs = json.loads(_META_FILE.read_text(encoding="utf-8"))
            if not docs:
                text = "Chưa có tài liệu nào."
            else:
                rows = [f"• {d['filename']} — {d['chunks']} chunks, {d['size']//1024}KB" for d in docs]
                text = f"Tổng {len(docs)} tài liệu:\n" + "\n".join(rows)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    if name == "get_server_info":
        info = {
            **SERVER_INFO,
            "timestamp": datetime.now().isoformat(),
            "indexed_chunks": len(retriever.chunks),
        }
        return {"content": [{"type": "text", "text": json.dumps(info, ensure_ascii=False, indent=2)}], "isError": False}

    return {"content": [{"type": "text", "text": f"Tool '{name}' không tồn tại."}], "isError": True}


def _handle_resources_list(_: dict) -> dict:
    docs = []
    if _META_FILE.exists():
        docs = json.loads(_META_FILE.read_text(encoding="utf-8"))
    return {
        "resources": [
            {
                "uri": f"doc://{d['id']}",
                "name": d["filename"],
                "description": f"{d['chunks']} chunks, {d['size']//1024}KB",
                "mimeType": "text/plain",
            }
            for d in docs
        ]
    }


def _handle_resources_read(params: dict) -> dict:
    uri = params.get("uri", "")
    doc_id = uri.replace("doc://", "")

    # Find chunks for this document
    chunks = [c for c in retriever.chunks if c["meta"].get("doc_id") == doc_id]
    if not chunks:
        return {"contents": [{"uri": uri, "text": "Tài liệu không tồn tại hoặc chưa được index."}]}

    text = "\n\n".join(c["text"] for c in chunks)
    return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": text}]}


# ── Dispatcher ────────────────────────────────────────────────────────────

_HANDLERS = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
    "resources/list": _handle_resources_list,
    "resources/read": _handle_resources_read,
}


@router.post("")
async def mcp_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(_err(None, -32700, "Parse error"), status_code=400)

    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    handler = _HANDLERS.get(method)
    if handler is None:
        return JSONResponse(_err(rpc_id, -32601, f"Method not found: {method}"))

    try:
        result = handler(params)
        return JSONResponse(_ok(rpc_id, result))
    except Exception as exc:
        return JSONResponse(_err(rpc_id, -32603, str(exc)))


@router.get("/info")
async def mcp_info():
    """Endpoint mô tả MCP server cho developer."""
    return {
        **SERVER_INFO,
        "transport": "HTTP/JSON-RPC 2.0",
        "endpoint": "POST /mcp",
        "methods": list(_HANDLERS.keys()),
        "indexed_chunks": len(retriever.chunks),
    }
