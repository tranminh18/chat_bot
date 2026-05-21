// ── Utilities ─────────────────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function getTime() {
  return new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

// ── Toast ──────────────────────────────────────────────────────────────────

const Toast = {
  container: null,

  init() {
    this.container = $("#toastContainer");
  },

  show(type, title, msg, duration = 3500) {
    const icons = { success: "✅", error: "❌", info: "ℹ️", warning: "⚠️" };
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `
      <span class="toast-icon">${icons[type] || "💬"}</span>
      <div class="toast-body">
        <div class="toast-title">${title}</div>
        ${msg ? `<div class="toast-msg">${msg}</div>` : ""}
      </div>`;
    this.container.appendChild(el);
    setTimeout(() => {
      el.classList.add("removing");
      setTimeout(() => el.remove(), 300);
    }, duration);
  },
};

// ── Document Manager ───────────────────────────────────────────────────────

const DocManager = {
  docs: [],

  async init() {
    await this.load();
    this.bindUpload();
  },

  async load() {
    try {
      const res = await fetch("/api/documents/");
      this.docs = await res.json();
      this.render();
    } catch {
      Toast.show("error", "Lỗi", "Không tải được danh sách tài liệu.");
    }
  },

  render() {
    const list = $("#docList");
    const empty = $("#docEmpty");
    const count = $("#docCount");

    count.textContent = this.docs.length;

    if (this.docs.length === 0) {
      empty.style.display = "block";
      Array.from(list.querySelectorAll(".doc-item")).forEach((el) => el.remove());
      return;
    }

    empty.style.display = "none";
    const existing = new Set(
      Array.from(list.querySelectorAll(".doc-item")).map((el) => el.dataset.id)
    );

    this.docs.forEach((doc) => {
      if (existing.has(doc.id)) return;
      const item = this._createItem(doc);
      list.appendChild(item);
    });

    Array.from(list.querySelectorAll(".doc-item")).forEach((el) => {
      if (!this.docs.find((d) => d.id === el.dataset.id)) el.remove();
    });
  },

  _createItem(doc) {
    const ext = doc.ext || "txt";
    const item = document.createElement("div");
    item.className = "doc-item";
    item.dataset.id = doc.id;
    item.innerHTML = `
      <div class="doc-icon ${ext}">${ext.toUpperCase()}</div>
      <div class="doc-info">
        <div class="doc-name" title="${doc.filename}">${doc.filename}</div>
        <div class="doc-meta">${formatSize(doc.size)} · ${doc.chunks} chunks</div>
      </div>
      <button class="doc-delete" title="Xoá tài liệu">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6l-1 14H6L5 6"/>
          <path d="M10 11v6M14 11v6"/>
        </svg>
      </button>`;
    item.querySelector(".doc-delete").onclick = (e) => {
      e.stopPropagation();
      this.delete(doc.id, doc.filename, item);
    };
    return item;
  },

  async delete(id, filename, itemEl) {
    if (!confirm(`Xoá "${filename}"?`)) return;
    try {
      const res = await fetch(`/api/documents/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error();
      this.docs = this.docs.filter((d) => d.id !== id);
      itemEl.style.transition = "opacity 0.2s, transform 0.2s";
      itemEl.style.opacity = "0";
      itemEl.style.transform = "translateX(-10px)";
      setTimeout(() => { itemEl.remove(); this.render(); }, 200);
      Toast.show("success", "Đã xoá", `"${filename}" đã được xoá.`);
    } catch {
      Toast.show("error", "Lỗi", "Không thể xoá tài liệu.");
    }
  },

  // ── Upload ────────────────────────────────────────────────────────────

  bindUpload() {
    const zone = $("#uploadZone");
    const input = $("#fileInput");
    const trigger = $("#uploadTrigger");

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      input.click();
    });

    zone.addEventListener("click", () => input.click());

    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      zone.classList.add("drag-over");
    });

    zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));

    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("drag-over");
      const files = Array.from(e.dataTransfer.files);
      if (files.length) this.upload(files[0]);
    });

    input.addEventListener("change", () => {
      if (input.files[0]) this.upload(input.files[0]);
      input.value = "";
    });
  },

  async upload(file) {
    const allowed = [".pdf", ".docx", ".txt"];
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!allowed.includes(ext)) {
      Toast.show("error", "Định dạng không hỗ trợ", `Chỉ nhận: ${allowed.join(", ")}`);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      Toast.show("error", "File quá lớn", "Tối đa 10MB.");
      return;
    }

    const progress = $("#uploadProgress");
    const fillEl = $("#progressFill");
    const pctEl = $("#progressPct");
    const fnEl = $("#progressFilename");
    const statusEl = $("#progressStatus");

    fnEl.textContent = file.name;
    fillEl.style.width = "0%";
    pctEl.textContent = "0%";
    statusEl.textContent = "Đang tải lên...";
    progress.style.display = "block";

    // Simulate upload progress (fetch doesn't expose upload progress easily)
    let pct = 0;
    const fakeProgress = setInterval(() => {
      pct = Math.min(pct + Math.random() * 8, 85);
      fillEl.style.width = pct + "%";
      pctEl.textContent = Math.round(pct) + "%";
    }, 150);

    const form = new FormData();
    form.append("file", file);

    try {
      statusEl.textContent = "Đang xử lý & tạo embeddings...";
      const res = await fetch("/api/documents/upload", { method: "POST", body: form });
      clearInterval(fakeProgress);

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload thất bại");
      }

      fillEl.style.width = "100%";
      pctEl.textContent = "100%";
      statusEl.textContent = "✅ Hoàn thành!";

      const doc = await res.json();
      this.docs.push(doc);
      this.render();
      Toast.show("success", "Upload thành công", `"${file.name}" — ${doc.chunks} chunks đã được index.`);

      setTimeout(() => { progress.style.display = "none"; }, 1500);
    } catch (err) {
      clearInterval(fakeProgress);
      progress.style.display = "none";
      Toast.show("error", "Upload thất bại", err.message);
    }
  },
};

// ── Chat Manager ───────────────────────────────────────────────────────────

const ChatManager = {
  isStreaming: false,

  init() {
    $("#clearBtn").addEventListener("click", () => this.clearHistory());
  },

  _msgContainer() {
    return $("#messages");
  },

  scrollToBottom() {
    const c = this._msgContainer();
    c.scrollTop = c.scrollHeight;
  },

  appendUserMsg(text) {
    const container = this._msgContainer();

    // Hide welcome card & suggestions on first message
    const welcome = container.querySelector(".welcome-card");
    if (welcome) welcome.remove();
    const sugg = $("#suggestions");
    if (sugg) sugg.style.display = "none";

    const row = document.createElement("div");
    row.className = "msg-row user";
    row.innerHTML = `
      <div class="msg-avatar">👤</div>
      <div class="msg-body">
        <div class="msg-bubble">${this._escHtml(text)}</div>
        <div class="msg-time">${getTime()}</div>
      </div>`;
    container.appendChild(row);
    this.scrollToBottom();
  },

  createBotRow() {
    const container = this._msgContainer();
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-body">
        <div class="msg-bubble streaming-cursor"></div>
        <div class="msg-time">${getTime()}</div>
      </div>`;
    container.appendChild(row);
    this.scrollToBottom();
    return row.querySelector(".msg-bubble");
  },

  showTyping() {
    const container = this._msgContainer();
    const el = document.createElement("div");
    el.className = "typing-row";
    el.id = "typingRow";
    el.innerHTML = `
      <div class="msg-avatar" style="background:linear-gradient(135deg,#3b82f6,#6366f1);border-radius:10px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">🤖</div>
      <div class="typing-bubble">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>`;
    container.appendChild(el);
    this.scrollToBottom();
  },

  hideTyping() {
    const el = $("#typingRow");
    if (el) el.remove();
  },

  async send(message) {
    if (this.isStreaming || !message.trim()) return;
    this.isStreaming = true;

    const sendBtn = $("#sendBtn");
    const input = $("#msgInput");
    sendBtn.disabled = true;
    input.disabled = true;

    this.appendUserMsg(message);
    this.showTyping();

    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      this.hideTyping();

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Lỗi không xác định" }));
        this._appendErrorMsg(err.detail);
        return;
      }

      const bubble = this.createBotRow();
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        bubble.innerHTML = DOMPurify.sanitize(marked.parse(buffer));
        this.scrollToBottom();
      }

      // Final render without cursor
      bubble.classList.remove("streaming-cursor");
      bubble.innerHTML = DOMPurify.sanitize(marked.parse(buffer));
      this.scrollToBottom();
    } catch {
      this.hideTyping();
      this._appendErrorMsg("Không thể kết nối máy chủ.");
    } finally {
      this.isStreaming = false;
      sendBtn.disabled = false;
      input.disabled = false;
      input.focus();
    }
  },

  _appendErrorMsg(text) {
    const container = this._msgContainer();
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-body">
        <div class="msg-bubble" style="border-color:rgba(239,68,68,0.4);color:#ef4444;">⚠️ ${this._escHtml(text)}</div>
        <div class="msg-time">${getTime()}</div>
      </div>`;
    container.appendChild(row);
    this.scrollToBottom();
  },

  clearHistory() {
    const container = this._msgContainer();
    container.innerHTML = `
      <div class="welcome-card">
        <div class="welcome-icon">🤖</div>
        <h2>Xin chào!</h2>
        <p>Upload tài liệu (PDF, DOCX, TXT) và đặt câu hỏi bất kỳ.<br/>Hệ thống sử dụng <strong>Hybrid Search</strong> kết hợp tìm kiếm ngữ nghĩa và từ khoá.</p>
        <div class="welcome-tips">
          <div class="tip">📄 Upload nhiều tài liệu cùng lúc</div>
          <div class="tip">🔍 Tìm kiếm thông minh với RAG</div>
          <div class="tip">💬 Hỗ trợ Tiếng Việt & English</div>
        </div>
      </div>`;
    const sugg = $("#suggestions");
    if (sugg) sugg.style.display = "";
  },

  _escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  },
};

// ── App Controller ─────────────────────────────────────────────────────────

const app = {
  async init() {
    marked.setOptions({ breaks: true, gfm: true });
    Toast.init();
    await DocManager.init();
    ChatManager.init();
    this._bindInput();
  },

  _bindInput() {
    const input = $("#msgInput");
    input.addEventListener("input", () => this._autoResize(input));
  },

  _autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  },

  autoResize(el) {
    this._autoResize(el);
  },

  handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      this.sendMessage();
    }
  },

  sendMessage() {
    const input = $("#msgInput");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    this._autoResize(input);
    ChatManager.send(text);
  },

  sendSuggestion(btn) {
    const text = btn.textContent.replace(/^[^\s]+\s/, "").trim();
    ChatManager.send(text);
  },
};

document.addEventListener("DOMContentLoaded", () => app.init());
