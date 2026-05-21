from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.memory import memory_store
from core.rag_pipeline import rag_stream

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    provider: str = "gemini"
    prompt_name: str = "rag_vi"


class ClearRequest(BaseModel):
    session_id: str = "default"


@router.post("/stream")
async def stream_chat(req: ChatRequest):
    if not req.message.strip():
        return StreamingResponse(
            iter([b"Vui l\xc3\xb2ng nh\xe1\xba\xadp c\xe2\x80\x8bu h\xe1\xbb\x8fi."]),
            media_type="text/plain; charset=utf-8",
        )

    async def generate():
        async for chunk in rag_stream(
            query=req.message.strip(),
            session_id=req.session_id,
            provider=req.provider,
            prompt_name=req.prompt_name,
        ):
            yield chunk.encode("utf-8")

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    return {"session_id": session_id, "history": memory_store.get(session_id)}


@router.post("/clear")
async def clear_history(req: ClearRequest):
    memory_store.clear(req.session_id)
    return {"message": "Đã xoá lịch sử hội thoại."}
