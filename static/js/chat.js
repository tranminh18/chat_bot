const messagesEl = document.getElementById("chatMessages");
const inputEl = document.getElementById("msgInput");
const sendBtn = document.getElementById("sendBtn");

marked.setOptions({ breaks: true, gfm: true });

function getTime() {
  return new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

function appendMessage(text, role) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "bot" ? "TA" : "B";

  const body = document.createElement("div");
  body.className = "msg-body";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  if (role === "bot") {
    bubble.innerHTML = marked.parse(text);
  } else {
    bubble.textContent = text;
  }

  const time = document.createElement("div");
  time.className = "msg-time";
  time.textContent = getTime();

  body.appendChild(bubble);
  body.appendChild(time);
  wrap.appendChild(avatar);
  wrap.appendChild(body);
  messagesEl.appendChild(wrap);
  scrollToBottom();
}

function showTyping() {
  const indicator = document.createElement("div");
  indicator.className = "typing-indicator";
  indicator.id = "typingIndicator";

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = "TA";

  const bubble = document.createElement("div");
  bubble.className = "typing-bubble";
  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("div");
    dot.className = "typing-dot";
    bubble.appendChild(dot);
  }

  indicator.appendChild(avatar);
  indicator.appendChild(bubble);
  messagesEl.appendChild(indicator);
  scrollToBottom();
}

function hideTyping() {
  const el = document.getElementById("typingIndicator");
  if (el) el.remove();
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = "";
  sendBtn.disabled = true;
  document.getElementById("quickReplies").style.display = "none";

  appendMessage(text, "user");
  showTyping();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    hideTyping();
    appendMessage(data.response || "Có lỗi xảy ra. Vui lòng thử lại!", "bot");
  } catch {
    hideTyping();
    appendMessage("Không thể kết nối máy chủ. Vui lòng thử lại!", "bot");
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

function sendQuick(text) {
  inputEl.value = text;
  sendMessage();
}
