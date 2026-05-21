from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.agent import agent_stream
from core.memory import memory_store

router = APIRouter()


class AgentRequest(BaseModel):
    message: str
    session_id: str = "default"


@router.post("/run")
async def run_agent(req: AgentRequest):
    if not req.message.strip():
        return {"error": "Empty message"}

    history = memory_store.get(req.session_id)

    async def generate():
        answer_buf = ""
        async for event_json in agent_stream(req.message.strip(), history):
            yield event_json.encode("utf-8")
            # Capture answer for memory
            import json as _json
            try:
                ev = _json.loads(event_json)
                if ev.get("type") == "answer":
                    answer_buf = ev.get("content", "")
            except Exception:
                pass
        # Update memory after stream
        if req.message.strip():
            memory_store.add(req.session_id, "user", req.message.strip())
        if answer_buf:
            memory_store.add(req.session_id, "assistant", answer_buf[:500])

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson; charset=utf-8",
    )
