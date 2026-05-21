from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.rag_pipeline import rag_stream

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/stream")
async def stream_chat(req: ChatRequest):
    if not req.message.strip():
        return StreamingResponse(
            iter([b"Vui l\xc3\xb2ng nh\xe1\xba\xadp c\xe2\x80\x8bu h\xe1\xbb\x8fi."]),
            media_type="text/plain; charset=utf-8",
        )

    async def generate():
        async for chunk in rag_stream(req.message.strip()):
            yield chunk.encode("utf-8")

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
