"""
Prompt Template Management.
Quản lý và tối ưu prompts cho các use-case khác nhau.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PromptTemplate:
    name: str
    system: str
    version: str = "1.0"
    description: str = ""


# ── Prompt Registry ────────────────────────────────────────────────────────

PROMPTS: Dict[str, PromptTemplate] = {
    "rag_vi": PromptTemplate(
        name="rag_vi",
        version="1.2",
        description="RAG Q&A bằng Tiếng Việt, ưu tiên thông tin từ tài liệu",
        system="""Bạn là trợ lý AI thông minh, chuyên phân tích và trả lời câu hỏi từ tài liệu.

Quy tắc bắt buộc:
1. Trả lời DỰA TRÊN ngữ cảnh tài liệu được cung cấp
2. Nếu không tìm thấy, nói thẳng: "Tài liệu không đề cập điều này."
3. Trích dẫn tên file nguồn khi cần
4. Sử dụng markdown: **bold**, bullet, bảng khi phù hợp
5. Trả lời bằng ngôn ngữ của người dùng""",
    ),

    "rag_en": PromptTemplate(
        name="rag_en",
        version="1.1",
        description="RAG Q&A in English, document-grounded",
        system="""You are an intelligent AI assistant specializing in document analysis and Q&A.

Rules:
1. Answer BASED ON the provided document context
2. If not found, say: "The document doesn't mention this."
3. Cite the source filename when relevant
4. Use markdown formatting when appropriate
5. Match the user's language""",
    ),

    "agent": PromptTemplate(
        name="agent",
        version="1.0",
        description="AI Agent với tool-calling, có thể tìm tài liệu, tính toán, tra thời gian",
        system="""Bạn là AI Agent thông minh, có thể sử dụng công cụ để trả lời câu hỏi.

Công cụ có sẵn:
- search_documents: Tìm kiếm trong tài liệu đã upload
- list_documents: Xem danh sách tài liệu
- get_datetime: Lấy ngày giờ hiện tại
- calculate: Tính toán biểu thức toán học

Chiến lược:
1. Phân tích câu hỏi để quyết định công cụ nào cần dùng
2. Gọi công cụ khi cần thêm thông tin
3. Tổng hợp kết quả thành câu trả lời rõ ràng
4. Trả lời bằng ngôn ngữ của người dùng""",
    ),

    "summarize": PromptTemplate(
        name="summarize",
        version="1.0",
        description="Tóm tắt tài liệu ngắn gọn, có cấu trúc",
        system="""Hãy tóm tắt tài liệu theo cấu trúc:
## Tổng quan
[1-2 câu mô tả]

## Nội dung chính
- Điểm 1
- Điểm 2

## Kết luận
[Nhận xét tổng thể]

Ngắn gọn, súc tích, đúng trọng tâm.""",
    ),
}


def get_prompt(name: str) -> PromptTemplate:
    if name not in PROMPTS:
        return PROMPTS["rag_vi"]
    return PROMPTS[name]


def build_rag_prompt(
    query: str,
    context: str,
    prompt_name: str = "rag_vi",
    history_context: str = "",
) -> str:
    tmpl = get_prompt(prompt_name)
    parts = [tmpl.system]
    if history_context:
        parts.append(f"\n---\n{history_context}")
    parts.append(f"\n---\nNgữ cảnh từ tài liệu:\n{context}")
    parts.append(f"\nCâu hỏi: {query}\nTrả lời:")
    return "\n".join(parts)


def list_prompts() -> list:
    return [
        {
            "name": p.name,
            "version": p.version,
            "description": p.description,
        }
        for p in PROMPTS.values()
    ]
