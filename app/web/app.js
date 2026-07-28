const state = {
  sessions: [],
  currentSession: null,
  running: false,
};

const elements = {
  healthDot: document.querySelector("#health-dot"),
  healthLabel: document.querySelector("#health-label"),
  healthDetail: document.querySelector("#health-detail"),
  sessionList: document.querySelector("#session-list"),
  newSession: document.querySelector("#new-session"),
  toolList: document.querySelector("#tool-list"),
  activeTitle: document.querySelector("#active-title"),
  activeId: document.querySelector("#active-id"),
  messages: document.querySelector("#messages"),
  composer: document.querySelector("#composer"),
  input: document.querySelector("#message-input"),
  send: document.querySelector("#send-button"),
  status: document.querySelector("#composer-status"),
  traceList: document.querySelector("#trace-list"),
  eventCount: document.querySelector("#event-count"),
  phases: [...document.querySelectorAll(".loop-node")],
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_) {
      // The status still provides a useful fallback.
    }
    throw new Error(detail);
  }
  return response.json();
}

function text(value) {
  return value == null ? "" : String(value);
}

function setStatus(message, isError = false) {
  elements.status.textContent = message;
  elements.status.classList.toggle("error", isError);
}

function setRunning(running) {
  state.running = running;
  elements.send.disabled = running || !state.currentSession;
  elements.input.disabled = running || !state.currentSession;
  if (running) {
    setStatus("Agent Runtime 正在执行…");
    setPhase("model");
  } else if (!elements.status.classList.contains("error")) {
    setStatus("Enter 换行，Ctrl + Enter 运行");
  }
}

function setPhase(active) {
  const order = ["input", "model", "tool", "continue"];
  const activeIndex = order.indexOf(active);
  elements.phases.forEach((node) => {
    const index = order.indexOf(node.dataset.phase);
    node.classList.toggle("active", node.dataset.phase === active);
    node.classList.toggle("done", activeIndex >= 0 && index < activeIndex);
  });
}

function markPhases(events) {
  const hasTool = events.some((event) => event.event_type === "tool_started");
  setPhase("continue");
  if (hasTool) {
    document.querySelector('[data-phase="tool"]').classList.add("done");
  }
}

function renderSessions() {
  elements.sessionList.replaceChildren();
  state.sessions.forEach((session) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `session-item${state.currentSession?.id === session.id ? " active" : ""}`;
    const title = document.createElement("strong");
    title.textContent = session.title;
    const id = document.createElement("code");
    id.textContent = session.id.slice(0, 8);
    button.append(title, id);
    button.addEventListener("click", () => selectSession(session));
    elements.sessionList.append(button);
  });
}

async function loadSessions() {
  state.sessions = await api("/api/sessions");
  if (!state.sessions.length) {
    const created = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ title: "Interview Demo" }),
    });
    state.sessions = [created];
  }
  const retained = state.sessions.find((item) => item.id === state.currentSession?.id);
  await selectSession(retained || state.sessions[0]);
}

async function selectSession(session) {
  state.currentSession = session;
  elements.activeTitle.textContent = session.title;
  elements.activeId.textContent = session.id;
  renderSessions();
  setRunning(false);
  await loadMessages();
}

async function createSession() {
  const ordinal = state.sessions.length + 1;
  const session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ title: `Session ${String(ordinal).padStart(2, "0")}` }),
  });
  state.sessions.unshift(session);
  await selectSession(session);
  elements.input.focus();
}

function messageCard(role, content, label = role.toUpperCase()) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const heading = document.createElement("div");
  heading.className = "message-label";
  const name = document.createElement("span");
  name.textContent = label;
  heading.append(name);
  const body = document.createElement("p");
  body.textContent = text(content);
  article.append(heading, body);
  return article;
}

function renderMessage(message) {
  if (message.role === "system") return;
  if (message.role === "assistant" && message.tool_calls.length) {
    const names = message.tool_calls.map((call) => call.name).join(", ");
    elements.messages.append(messageCard("tool", `requested: ${names}`, "TOOL REQUEST"));
    if (message.content) elements.messages.append(messageCard("assistant", message.content));
    return;
  }
  if (message.role === "tool") {
    let rendered = message.content;
    try {
      const result = JSON.parse(message.content);
      rendered = `${result.tool_name}: ${result.content}`;
    } catch (_) {
      // Render the bounded server text if it is not JSON.
    }
    elements.messages.append(messageCard("tool", rendered, "TOOL RESULT"));
    return;
  }
  elements.messages.append(messageCard(message.role, message.content));
}

async function loadMessages() {
  const messages = await api(`/api/sessions/${state.currentSession.id}/messages`);
  elements.messages.replaceChildren();
  if (!messages.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<span>◌</span><h3>Session 已就绪</h3><p>发送一个任务，观察 Agent Loop 与 Trace。</p>";
    elements.messages.append(empty);
  } else {
    messages.forEach(renderMessage);
  }
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function compactPayload(payload) {
  const json = JSON.stringify(payload || {});
  return json.length > 150 ? `${json.slice(0, 150)}…` : json;
}

function renderTrace(events) {
  elements.traceList.replaceChildren();
  elements.eventCount.textContent = String(events.length).padStart(2, "0");
  events.forEach((event) => {
    const row = document.createElement("div");
    const isTool = event.event_type.startsWith("tool_");
    row.className = `trace-event${isTool ? " tool" : ""}${event.status === "failed" ? " failed" : ""}`;
    const round = document.createElement("span");
    round.className = "round";
    round.textContent = event.round ? `R${event.round}` : "•";
    const detail = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = event.event_type;
    const payload = document.createElement("p");
    payload.textContent = compactPayload(event.payload);
    detail.append(title, payload);
    row.append(round, detail);
    elements.traceList.append(row);
  });
  markPhases(events);
}

async function sendMessage(event) {
  event.preventDefault();
  if (state.running || !state.currentSession) return;
  const value = elements.input.value.trim();
  if (!value) return;
  setPhase("input");
  elements.input.value = "";
  setRunning(true);
  try {
    const result = await api(`/api/sessions/${state.currentSession.id}/runs`, {
      method: "POST",
      body: JSON.stringify({ text: value }),
    });
    await loadMessages();
    renderTrace(result.events);
    if (result.status === "failed") setStatus(result.final_answer, true);
  } catch (error) {
    setStatus(error.message, true);
    setPhase("input");
  } finally {
    setRunning(false);
    elements.input.focus();
  }
}

async function loadHealthAndTools() {
  try {
    const [health, tools] = await Promise.all([api("/api/health"), api("/api/tools")]);
    elements.healthDot.classList.add(health.llm_configured ? "ok" : "warn");
    elements.healthLabel.textContent = health.llm_configured ? "RUNTIME READY" : "LLM NOT SET";
    elements.healthDetail.textContent = `${health.storage} / v${health.version}`;
    elements.toolList.replaceChildren();
    tools.forEach((tool) => {
      const chip = document.createElement("span");
      chip.className = "tool-chip";
      chip.textContent = tool.function.name;
      chip.title = tool.function.description;
      elements.toolList.append(chip);
    });
  } catch (error) {
    elements.healthLabel.textContent = "RUNTIME OFFLINE";
    elements.healthDetail.textContent = error.message;
  }
}

elements.newSession.addEventListener("click", () => createSession().catch((error) => setStatus(error.message, true)));
elements.composer.addEventListener("submit", sendMessage);
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    elements.composer.requestSubmit();
  }
});

Promise.all([loadHealthAndTools(), loadSessions()]).catch((error) => setStatus(error.message, true));
