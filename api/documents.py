import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from core.document_processor import SUPPORTED_EXTENSIONS, extract_text
from core.hybrid_retriever import retriever
from core.rag_pipeline import index_document

router = APIRouter()

UPLOADS = Path("data/uploads")
META_FILE = Path("data/documents.json")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _load_meta() -> list:
    return json.loads(META_FILE.read_text(encoding="utf-8")) if META_FILE.exists() else []


def _save_meta(docs: list) -> None:
    META_FILE.parent.mkdir(parents=True, exist_ok=True)
    META_FILE.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")


@router.post("/upload", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Định dạng không hỗ trợ. Chỉ nhận: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File quá lớn. Tối đa 10MB.")

    doc_id = str(uuid.uuid4())
    UPLOADS.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS / f"{doc_id}{ext}"
    dest.write_bytes(content)

    try:
        text = extract_text(str(dest), file.filename)
        if not text.strip():
            dest.unlink()
            raise HTTPException(422, "Không đọc được văn bản từ tài liệu.")

        num_chunks = index_document(text, doc_id, file.filename)

        doc_info = {
            "id": doc_id,
            "filename": file.filename,
            "size": len(content),
            "chunks": num_chunks,
            "ext": ext.lstrip("."),
        }
        docs = _load_meta()
        docs.append(doc_info)
        _save_meta(docs)

        return JSONResponse(doc_info, status_code=201)

    except HTTPException:
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"Lỗi xử lý tài liệu: {exc}") from exc


@router.get("/")
async def list_documents():
    return _load_meta()


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    docs = _load_meta()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(404, "Không tìm thấy tài liệu.")

    for ext in SUPPORTED_EXTENSIONS:
        p = UPLOADS / f"{doc_id}{ext}"
        p.unlink(missing_ok=True)

    retriever.delete_document(doc_id)
    _save_meta([d for d in docs if d["id"] != doc_id])
    return {"message": "Đã xóa tài liệu thành công."}
