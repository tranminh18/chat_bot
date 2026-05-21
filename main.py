from pathlib import Path

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api import chat, documents
from api import agent as agent_api
from core.llm_factory import get_available_providers
from core.prompts import list_prompts
from mcp_server import router as mcp_router

for d in ["data/uploads", "data/vector_store"]:
    Path(d).mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Document Intelligence Chatbot",
    description=(
        "RAG-powered document Q&A — Hybrid Search (FAISS + BM25) · "
        "Multi-LLM · AI Agent · MCP Server · Conversation Memory"
    ),
    version="2.0.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── API Routers ────────────────────────────────────────────────────────────
app.include_router(documents.router,   prefix="/api/documents",  tags=["Documents"])
app.include_router(chat.router,        prefix="/api/chat",        tags=["RAG Chat"])
app.include_router(agent_api.router,   prefix="/api/agent",       tags=["AI Agent"])
app.include_router(mcp_router,         prefix="/mcp",             tags=["MCP Server"])


# ── Pages ──────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Meta endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/providers")
async def providers():
    """Trả về danh sách LLM provider đã cấu hình."""
    return get_available_providers()


@app.get("/api/prompts")
async def prompts():
    """Trả về danh sách prompt templates."""
    return list_prompts()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})
