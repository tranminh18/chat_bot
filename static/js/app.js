/* ═══════════════════════════════════════════════════════════════════════════
   Document Intelligence Chatbot – Frontend App
   Features: Multi-LLM, RAG Chat, AI Agent (tool-calling), MCP console, Memory
════════════════════════════════════════════════════════════════════════════ */

const $ = (s) => document.querySelector(s);

// ── State ──────────────────────────────────────────────────────────────────

const State = {
  mode: "rag",               // "rag" | "agent"
  provider: "gemini",
  promptName: "rag_vi",
  sessionId: `sess_${Date.now()}`,
  memoryEnabled: true,
  isBusy: false,
};

// ── Utilities ──────────────────────────────────────────────────────────────

function getTime() {
  return new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}
function formatBytes(b) {
  return b < 1024 ? `${b}B` : b < 1048576 ? `${(b / 1024).toFixed(1)}KB` : `${(b / 1048576).toFixed(1)}MB`;
}
function escHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ── Toast ──────────────────────────────────────────────────────────────────

const Toast = {
  show(type, title, msg = "", dur = 3500) {
    const icons = { success: "✅", error: "❌", info: "ℹ️", warning: "⚠️" };
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `<span class="toast-icon">${icons[type] || "💬"}</span>
      <div><div class="toast-title">${escHtml(title)}</div>${msg ? `<div class="toast-msg">${escHtml(msg)}</div>` : ""}</div>`;
    $("#toastContainer").appendChild(el);
    setTimeout(() => {
      el.classList.add("removing");
      setTimeout(() => el.remove(), 280);
    }, dur);
  },
};

// ── Provider Setup ─────────────────────────────────────────────────────────

const ProviderManager = {
  async init() {
    try {
      const data = await fetch("/api/providers").then((r) => r.json());
      document.querySelectorAll(".provider-btn").forEach((btn) => {
        const p = btn.dataset.provider;
        if (data[p]) {
          btn.classList.remove("disabled");
        } else {
          btn.classList.add("disabled");
          btn.title = `${p} API key chưa cấu hình`;
        }
      });
    } catch {
      /* ignore – providers shown as-is */
    }

    document.querySelectorAll(".provider-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.classList.contains("disabled")) {
          Toast.show("warning", "Provider chưa cấu hình", "Thêm API key vào .env để dùng.");
          return;
        }
        document.querySelectorAll(".provider-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        State.provider = btn.dataset.provider;
        Toast.show("info", `Đã chuyển sang ${btn.querySelector(".provider-name").textContent}`);
      });
    });
  },
};

// ── Mode Tabs ──────────────────────────────────────────────────────────────

const ModeTabs = {
  DESCS: {
    rag:   "RAG · Hybrid Search (FAISS + BM25) · Conversation Memory",
    agent: "AI Agent · Tool Calling · search_documents / calculate / get_datetime",
    mcp:   "MCP Server · JSON-RPC 2.0 · Công cụ & tài nguyên cho LLM",
  },

  init() {
    document.querySelectorAll(".mode-tab").forEach((tab) => {
      tab.addEventListener("click", () => this.setMode(tab.dataset.mode));
    });
  },

  setMode(mode) {
    State.mode = mode;
    document.querySelectorAll(".mode-tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === mode));
    $("#modeDesc").textContent = this.DESCS[mode] || "";
    $("#modeIndicator").textContent = mode.toUpperCase();

    const mcpPanel = $("#mcpPanel");
    const chatPanel = $(".chat-panel");

    if (mode === "mcp") {
      mcpPanel.style.display = "flex";
      mcpPanel.style.flexDirection = "column";
      chatPanel.style.display = "none";
    } else {
      mcpPanel.style.display = "none";
      chatPanel.style.display = "flex";
    }
  },
};

// ── Document Manager ───────────────────────────────────────────────────────

const DocManager = {
  docs: [],

  async init() {
    await this.load();
    this._bindUpload();
  },

  async load() {
    try {
      this.docs = await fetch("/api/documents/").then((r) => r.json());
      this._render();
    } catch {
      Toast.show("error", "Lỗi", "Không tải được danh sách tài liệu.");
    }
  },

  _render() {
    const list = $("#docList");
    const empty = $("#docEmpty");
    $("#docCount").textContent = this.docs.length;
    empty.style.display = this.docs.length ? "none" : "block";

    // Remove items no longer in docs
    list.querySelectorAll(".doc-item").forEach((el) => {
      if (!this.docs.find((d) => d.id === el.dataset.id)) {
        el.style.transition = "opacity 0.2s";
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 200);
      }
    });

    // Add new items
    const existing = new Set([...list.querySelectorAll(".doc-item")].map((el) => el.dataset.id));
    this.docs.forEach((doc) => {
      if (!existing.has(doc.id)) list.appendChild(this._makeItem(doc));
    });
  },

  _makeItem(doc) {
    const ext = doc.ext || "txt";
    const el = document.createElement("div");
    el.className = "doc-item";
    el.dataset.id = doc.id;
    el.innerHTML = `
      <div class="doc-icon ${ext}">${ext.toUpperCase()}</div>
      <div class="doc-info">
        <div class="doc-name" title="${escHtml(doc.filename)}">${escHtml(doc.filename)}</div>
        <div class="doc-meta">${formatBytes(doc.size)} · ${doc.chunks} chunks</div>
      </div>
      <button class="doc-delete" title="Xoá">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6l-1 14H6L5 6"/>
        </svg>
      </button>`;
    el.querySelector(".doc-delete").onclick = (e) => {
      e.stopPropagation();
      this._delete(doc.id, doc.filename, el);
    };
    return el;
  },

  async _delete(id, name, el) {
    if (!confirm(`Xoá "${name}"?`)) return;
    try {
      const res = await fetch(`/api/documents/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error();
      this.docs = this.docs.filter((d) => d.id !== id);
      el.style.transition = "opacity 0.2s, transform 0.2s";
      el.style.opacity = "0"; el.style.transform = "translateX(-8px)";
      setTimeout(() => { el.remove(); this._render(); }, 200);
      Toast.show("success", "Đã xoá", `"${name}" đã được xoá.`);
    } catch {
      Toast.show("error", "Lỗi", "Không thể xoá tài liệu.");
    }
  },

  _bindUpload() {
    const zone = $("#uploadZone"), input = $("#fileInput");
    $("#uploadTrigger").onclick = (e) => { e.stopPropagation(); input.click(); };
    zone.onclick = () => input.click();
    zone.ondragover = (e) => { e.preventDefault(); zone.classList.add("drag-over"); };
    zone.ondragleave = () => zone.classList.remove("drag-over");
    zone.ondrop = (e) => { e.preventDefault(); zone.classList.remove("drag-over"); if (e.dataTransfer.files[0]) this._upload(e.dataTransfer.files[0]); };
    input.onchange = () => { if (input.files[0]) this._upload(input.files[0]); input.value = ""; };
  },

  async _upload(file) {
    const allowed = [".pdf", ".docx", ".txt"];
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!allowed.includes(ext)) { Toast.show("error", "Định dạng không hỗ trợ", allowed.join(", ")); return; }
    if (file.size > 10 * 1024 * 1024) { Toast.show("error", "File quá lớn", "Tối đa 10MB."); return; }

    const prog = $("#uploadProgress"), fill = $("#progressFill");
    const pct = $("#progressPct"), fn = $("#progressFilename"), status = $("#progressStatus");
    fn.textContent = file.name; fill.style.width = "0%"; pct.textContent = "0%";
    status.textContent = "Đang tải lên…"; prog.style.display = "block";

    let p = 0;
    const tick = setInterval(() => { p = Math.min(p + Math.random() * 7, 82); fill.style.width = p + "%"; pct.textContent = Math.round(p) + "%"; }, 180);

    try {
      status.textContent = "Đang tạo embeddings…";
      const form = new FormData(); form.append("file", file);
      const res = await fetch("/api/documents/upload", { method: "POST", body: form });
      clearInterval(tick);

      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Upload thất bại"); }

      fill.style.width = "100%"; pct.textContent = "100%"; status.textContent = "✅ Hoàn thành!";
      const doc = await res.json();
      this.docs.push(doc); this._render();
      Toast.show("success", "Upload thành công", `"${file.name}" — ${doc.chunks} chunks indexed.`);
      setTimeout(() => (prog.style.display = "none"), 1600);
    } catch (err) {
      clearInterval(tick); prog.style.display = "none";
      Toast.show("error", "Upload thất bại", err.message);
    }
  },
};

// ── Chat Manager ───────────────────────────────────────────────────────────

const Chat = {
  _msgs() { return $("#messages"); },

  scrollBottom() {
    const c = this._msgs(); c.scrollTop = c.scrollHeight;
  },

  _hideWelcome() {
    const w = $("#welcomeCard"); if (w) w.remove();
    const s = $("#suggestions"); if (s) s.style.display = "none";
  },

  appendUser(text) {
    this._hideWelcome();
    const row = document.createElement("div");
    row.className = "msg-row user";
    row.innerHTML = `
      <div class="msg-avatar">👤</div>
      <div class="msg-body">
        <div class="msg-bubble">${escHtml(text)}</div>
        <div class="msg-time">${getTime()}</div>
      </div>`;
    this._msgs().appendChild(row);
    this.scrollBottom();
  },

  createBotBubble() {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-body">
        <div class="msg-bubble streaming-cursor"></div>
        <div class="msg-time">${getTime()}</div>
      </div>`;
    this._msgs().appendChild(row);
    this.scrollBottom();
    return row.querySelector(".msg-bubble");
  },

  showTyping() {
    const el = document.createElement("div");
    el.className = "typing-row"; el.id = "typingRow";
    el.innerHTML = `
      <div class="msg-avatar" style="background:linear-gradient(135deg,#3b82f6,#6366f1);border-radius:9px;width:34px;height:34px;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;align-self:flex-end;">🤖</div>
      <div class="typing-bubble"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>`;
    this._msgs().appendChild(el);
    this.scrollBottom();
  },

  hideTyping() { const el = $("#typingRow"); if (el) el.remove(); },

  appendError(text) {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-body">
        <div class="msg-bubble" style="border-color:rgba(239,68,68,0.4);color:#ef4444;">⚠️ ${escHtml(text)}</div>
        <div class="msg-time">${getTime()}</div>
      </div>`;
    this._msgs().appendChild(row);
    this.scrollBottom();
  },

  updateMetrics(latencyMs, tokens) {
    const chip = $("#metricsChip");
    $("#metricLatency").textContent = `${latencyMs}ms`;
    $("#metricTokens").textContent = `${tokens} tok`;
    chip.style.display = "flex";
  },

  // ── RAG streaming ───────────────────────────────────────────────────────

  async sendRag(message) {
    this.showTyping();
    const payload = {
      message,
      session_id: State.memoryEnabled ? State.sessionId : "anon",
      provider: State.provider,
      prompt_name: State.promptName,
    };
    const t0 = Date.now();
    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      this.hideTyping();
      if (!res.ok) { const e = await res.json(); this.appendError(e.detail); return; }

      const bubble = this.createBotBubble();
      const reader = res.body.getReader();
      const dec = new TextDecoder("utf-8");
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        bubble.innerHTML = DOMPurify.sanitize(marked.parse(buf));
        this.scrollBottom();
      }
      bubble.classList.remove("streaming-cursor");
      bubble.innerHTML = DOMPurify.sanitize(marked.parse(buf));
      this.updateMetrics(Date.now() - t0, Math.round(buf.length / 4));
    } catch {
      this.hideTyping();
      this.appendError("Không thể kết nối máy chủ.");
    }
  },

  // ── Agent streaming (NDJSON events) ────────────────────────────────────

  async sendAgent(message) {
    this.showTyping();
    const t0 = Date.now();
    try {
      const res = await fetch("/api/agent/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: State.sessionId }),
      });
      this.hideTyping();
      if (!res.ok) { this.appendError("Agent thất bại."); return; }

      // Create trace container + answer bubble together
      const wrapper = document.createElement("div");
      wrapper.style.display = "contents";

      const traceEl = document.createElement("div");
      traceEl.className = "agent-trace";
      traceEl.innerHTML = `<div style="font-size:11px;font-weight:700;color:var(--accent);margin-bottom:4px;">🔧 Agent Trace</div>`;

      // Row for final answer
      const ansRow = document.createElement("div");
      ansRow.className = "msg-row bot";
      ansRow.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-body">
          <div class="msg-bubble streaming-cursor"></div>
          <div class="msg-time">${getTime()}</div>
        </div>`;

      const msgs = this._msgs();
      this._hideWelcome();
      msgs.appendChild(traceEl);
      msgs.appendChild(ansRow);
      this.scrollBottom();

      const bubble = ansRow.querySelector(".msg-bubble");
      const reader = res.body.getReader();
      const dec = new TextDecoder("utf-8");
      let rawBuf = "";
      let toolCalls = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        rawBuf += dec.decode(value, { stream: true });

        // Parse complete NDJSON lines
        const lines = rawBuf.split("\n");
        rawBuf = lines.pop(); // keep incomplete line

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const ev = JSON.parse(line);
            this._handleAgentEvent(ev, traceEl, bubble);
            if (ev.type === "metrics") {
              this.updateMetrics(ev.latency_ms, ev.token_estimate);
              toolCalls = ev.tool_calls || 0;
            }
          } catch { /* skip malformed */ }
        }
        this.scrollBottom();
      }

      bubble.classList.remove("streaming-cursor");
      if (traceEl.querySelectorAll(".trace-item").length === 0) {
        traceEl.remove(); // no tool calls → remove empty trace
      }
    } catch {
      this.hideTyping();
      this.appendError("Không thể kết nối Agent.");
    }
  },

  _handleAgentEvent(ev, traceEl, bubble) {
    if (ev.type === "tool_call") {
      const item = document.createElement("div");
      item.className = "trace-item";
      item.innerHTML = `
        <span class="trace-icon">🔧</span>
        <div class="trace-content">
          <div class="trace-tool">${escHtml(ev.tool)}</div>
          <div class="trace-args">${escHtml(JSON.stringify(ev.args || {}))}</div>
        </div>`;
      traceEl.appendChild(item);
    } else if (ev.type === "tool_result") {
      const last = traceEl.querySelector(".trace-item:last-child");
      if (last) {
        const res = document.createElement("div");
        res.className = "trace-result";
        res.textContent = "→ " + (ev.result || "").slice(0, 120) + (ev.result && ev.result.length > 120 ? "…" : "");
        last.querySelector(".trace-content").appendChild(res);
      }
    } else if (ev.type === "answer") {
      bubble.classList.remove("streaming-cursor");
      bubble.innerHTML = DOMPurify.sanitize(marked.parse(ev.content || ""));
    } else if (ev.type === "error") {
      bubble.classList.remove("streaming-cursor");
      bubble.style.color = "#ef4444";
      bubble.textContent = "⚠️ " + ev.content;
    }
  },
};

// ── MCP Console ─────────────────────────────────────────────────────────────

const McpConsole = {
  METHOD_PARAMS: {
    "initialize":         '{}',
    "tools/list":         '{}',
    "tools/call":         '{"name":"search_documents","arguments":{"query":"AI chatbot"}}',
    "resources/list":     '{}',
  },

  init() {
    $("#mcpMethod").addEventListener("change", () => {
      const m = $("#mcpMethod").value;
      $("#mcpParams").value = this.METHOD_PARAMS[m] || "{}";
    });
    $("#mcpParams").value = this.METHOD_PARAMS["initialize"];
  },

  async run() {
    const method = $("#mcpMethod").value;
    let params;
    try { params = JSON.parse($("#mcpParams").value || "{}"); }
    catch { Toast.show("error", "JSON không hợp lệ"); return; }

    const body = { jsonrpc: "2.0", id: Date.now(), method, params };
    try {
      const res = await fetch("/mcp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      $("#mcpResult").textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      $("#mcpResult").textContent = `Error: ${err.message}`;
    }
  },
};

// ── Main App Controller ────────────────────────────────────────────────────

const app = {
  async init() {
    marked.setOptions({ breaks: true, gfm: true });

    await Promise.all([ProviderManager.init(), DocManager.init()]);
    ModeTabs.init();
    McpConsole.init();
    this._bindControls();
  },

  _bindControls() {
    // Prompt select
    $("#promptSelect").addEventListener("change", (e) => {
      State.promptName = e.target.value;
    });

    // Memory toggle
    $("#memoryCheck").addEventListener("change", (e) => {
      State.memoryEnabled = e.target.checked;
      Toast.show("info", State.memoryEnabled ? "Memory BẬT" : "Memory TẮT");
    });

    // Clear chat
    $("#clearBtn").addEventListener("click", async () => {
      this._resetMessages();
      await fetch("/api/chat/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: State.sessionId }),
      }).catch(() => {});
      Toast.show("success", "Đã xoá lịch sử chat");
    });
  },

  _resetMessages() {
    $("#messages").innerHTML = `
      <div class="welcome-card" id="welcomeCard">
        <div class="welcome-icon">🧠</div>
        <h2>Document Intelligence</h2>
        <p>Upload tài liệu PDF, DOCX, TXT và đặt câu hỏi.<br/>
        Chọn <strong>AI Agent</strong> để kích hoạt tool-calling.</p>
        <div class="feature-grid">
          <div class="feature-item"><span>🔍</span><span>Hybrid Search</span></div>
          <div class="feature-item"><span>🤖</span><span>AI Agent</span></div>
          <div class="feature-item"><span>🔌</span><span>MCP Server</span></div>
          <div class="feature-item"><span>💬</span><span>Memory</span></div>
        </div>
      </div>`;
    $("#suggestions").style.display = "";
    $("#metricsChip").style.display = "none";
  },

  handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.sendMessage(); }
  },

  autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 130) + "px";
  },

  async sendMessage() {
    const input = $("#msgInput");
    const text = input.value.trim();
    if (!text || State.isBusy) return;

    input.value = "";
    this.autoResize(input);
    State.isBusy = true;
    $("#sendBtn").disabled = true;
    input.disabled = true;

    Chat.appendUser(text);

    try {
      if (State.mode === "agent") {
        await Chat.sendAgent(text);
      } else {
        await Chat.sendRag(text);
      }
    } finally {
      State.isBusy = false;
      $("#sendBtn").disabled = false;
      input.disabled = false;
      input.focus();
    }
  },

  useSuggestion(btn) {
    const text = btn.textContent.replace(/^[^\s]+\s/, "").trim();
    $("#msgInput").value = text;
    this.sendMessage();
  },

  runMcp() { McpConsole.run(); },
};

document.addEventListener("DOMContentLoaded", () => app.init());
