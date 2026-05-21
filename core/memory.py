"""
Session-based Conversation Memory.
Lưu lịch sử hội thoại theo session_id, giới hạn số lượt để tránh context quá dài.
Production: thay bằng Redis hoặc PostgreSQL.
"""

import time
from collections import deque
from threading import Lock
from typing import Dict, List

from core.config import settings


class SessionMemory:
    def __init__(self, max_turns: int = 8):
        self._store: Dict[str, deque] = {}
        self._ts: Dict[str, float] = {}
        self._lock = Lock()
        self.max_turns = max_turns

    def add(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = deque(maxlen=self.max_turns * 2)
            self._store[session_id].append({"role": role, "content": content})
            self._ts[session_id] = time.time()

    def get(self, session_id: str) -> List[dict]:
        with self._lock:
            return list(self._store.get(session_id, []))

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)
            self._ts.pop(session_id, None)

    def as_context_string(self, session_id: str, max_chars: int = 1500) -> str:
        """Định dạng history thành chuỗi context cho prompt."""
        history = self.get(session_id)
        if not history:
            return ""
        lines = []
        for msg in history[-6:]:
            role = "Người dùng" if msg["role"] == "user" else "Trợ lý"
            text = msg["content"][:300].replace("\n", " ")
            lines.append(f"{role}: {text}")
        return "Lịch sử hội thoại:\n" + "\n".join(lines)

    def as_langchain_messages(self, session_id: str):
        """Chuyển history thành LangChain message objects."""
        from langchain_core.messages import HumanMessage, AIMessage
        messages = []
        for msg in self.get(session_id)[-6:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
        return messages


# Global singleton
memory_store = SessionMemory(max_turns=settings.memory_max_turns)
