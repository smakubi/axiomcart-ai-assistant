const elements = {
  serviceStatus: document.querySelector("#service-status"),
  versionChip: document.querySelector("#version-chip"),
  transcript: document.querySelector("#transcript"),
  promptStrip: document.querySelector("#prompt-strip"),
  composer: document.querySelector("#composer"),
  input: document.querySelector("#message-input"),
  sendButton: document.querySelector("#send-button"),
  resetButton: document.querySelector("#reset-button"),
  interruptBanner: document.querySelector("#interrupt-banner"),
  composerHint: document.querySelector("#composer-hint"),
  runBadge: document.querySelector("#run-badge"),
  routeExplanation: document.querySelector("#route-explanation p"),
  eventList: document.querySelector("#event-list"),
  stateThread: document.querySelector("#state-thread"),
  stateRoute: document.querySelector("#state-route"),
  stateResults: document.querySelector("#state-results"),
  stateCheckpoint: document.querySelector("#state-checkpoint"),
  settingsDialog: document.querySelector("#settings-dialog"),
  settingsOpen: document.querySelector("#settings-open"),
  settingsForm: document.querySelector("#settings-form"),
  settingsSave: document.querySelector("#settings-save"),
  apiKeyInput: document.querySelector("#api-key-input"),
  modelInput: document.querySelector("#model-input"),
  keyVisibility: document.querySelector("#key-visibility"),
  serverKeyNote: document.querySelector("#server-key-note"),
};

const nodeLabels = {
  orchestrator: "Orchestrator",
  product_agent: "Product agent",
  support_agent: "Support agent",
  synthesizer: "Synthesizer",
  search_product_catalog: "Catalog search",
  get_order_status: "Order lookup",
  escalate_to_human: "Human escalation",
};

const state = {
  threadId: crypto.randomUUID(),
  messages: [],
  events: [],
  route: [],
  results: [],
  pendingResume: false,
  running: false,
  serverKeyConfigured: false,
  controller: null,
};

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function getApiKey() {
  return sessionStorage.getItem("axiomcart-openai-key") || "";
}

function getModel() {
  return localStorage.getItem("axiomcart-model") || "gpt-5.4-mini";
}

function setRunBadge(label, status = "ready") {
  elements.runBadge.textContent = label;
  elements.runBadge.dataset.status = status;
}

function renderWelcome() {
  elements.transcript.innerHTML = `
    <div class="welcome-state">
      <div>
        <span class="welcome-orb" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M4 7h16l-2 11H6L4 7Zm3 0a5 5 0 0 1 10 0M9 21h.01M15 21h.01" /></svg>
        </span>
        <h3>Your storefront is ready</h3>
        <p>Choose an example above or ask your own question. The graph inspector will light up as Python runs each node.</p>
      </div>
    </div>`;
}

function renderMessages() {
  if (!state.messages.length) {
    renderWelcome();
    return;
  }
  elements.transcript.innerHTML = state.messages.map((message) => `
    <article class="message message-${message.role}">
      ${message.role === "assistant" ? '<span class="avatar" aria-hidden="true">AC</span>' : ""}
      <div class="message-body">
        <div class="message-meta">${message.role === "assistant" ? "AxiomCart" : "You"}</div>
        <div class="bubble">${escapeHtml(message.content)}</div>
      </div>
    </article>`).join("");
  if (state.running) {
    elements.transcript.insertAdjacentHTML("beforeend", `
      <article class="message message-assistant" id="typing-message">
        <span class="avatar" aria-hidden="true">AC</span>
        <div class="message-body"><div class="message-meta">Working</div><div class="bubble typing-bubble"><span></span><span></span><span></span></div></div>
      </article>`);
  }
  elements.transcript.scrollTop = elements.transcript.scrollHeight;
}

function resetNodes() {
  document.querySelectorAll("[data-node]").forEach((card) => {
    card.dataset.status = "ready";
    card.querySelector(".node-status").textContent = "Ready";
  });
}

function updateNode(node, status, detail = "") {
  const card = document.querySelector(`[data-node="${node}"]`);
  if (card) {
    card.dataset.status = status;
    const statusLabel = { active: "Active", complete: "Done", waiting: "Paused", skipped: "Skipped", error: "Error", ready: "Ready" }[status] || status;
    card.querySelector(".node-status").textContent = statusLabel;
    if (detail) card.title = detail;
  }
}

function addEvent(event) {
  state.events.push({ ...event, at: new Date() });
  state.events = state.events.slice(-30);
  elements.eventList.innerHTML = state.events.slice().reverse().map((item) => `
    <li>
      <strong>${escapeHtml(nodeLabels[item.node] || item.node || "Graph")}</strong>
      ${escapeHtml(item.detail || item.status || "Update")}
      <time>${item.at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time>
    </li>`).join("");
}

function updateStatePanel(checkpoint) {
  elements.stateThread.textContent = state.threadId;
  elements.stateRoute.textContent = JSON.stringify(state.route);
  elements.stateResults.textContent = `${state.results.length} item${state.results.length === 1 ? "" : "s"}`;
  elements.stateCheckpoint.textContent = checkpoint;
}

function configureRunStart() {
  state.running = true;
  state.events = [];
  state.route = [];
  state.results = [];
  resetNodes();
  updateNode("orchestrator", "active");
  setRunBadge("Running", "running");
  elements.sendButton.disabled = true;
  elements.promptStrip.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  elements.eventList.innerHTML = "";
  updateStatePanel("running");
  renderMessages();
}

function configureRunEnd(status = "complete") {
  state.running = false;
  state.controller = null;
  elements.sendButton.disabled = false;
  elements.promptStrip.querySelectorAll("button").forEach((button) => { button.disabled = false; });
  setRunBadge(status === "complete" ? "Complete" : status === "waiting" ? "Paused" : "Error", status);
  renderMessages();
  elements.input.focus();
}

function applyGraphEvent(event) {
  updateNode(event.node, event.status, event.detail);
  addEvent(event);
  if (event.node === "orchestrator" && Array.isArray(event.route)) {
    state.route = event.route;
    ["product_agent", "support_agent"].forEach((agent) => {
      if (!state.route.includes(agent)) updateNode(agent, "skipped");
    });
    elements.routeExplanation.textContent = event.detail;
    updateStatePanel("running");
  }
  if (event.status === "waiting") {
    setRunBadge("Waiting", "waiting");
    updateStatePanel("interrupted");
  }
}

function showError(message) {
  state.messages.push({ role: "assistant", content: `I couldn't finish that run: ${message}` });
  document.querySelectorAll("[data-node][data-status=" + '"active"' + "]").forEach((card) => updateNode(card.dataset.node, "error"));
  configureRunEnd("error");
}

function historyForApi() {
  return state.messages.slice(-20).map(({ role, content }) => ({ role, content }));
}

async function readStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) handleServerEvent(JSON.parse(line));
    }
    if (done) break;
  }
  if (buffer.trim()) handleServerEvent(JSON.parse(buffer));
}

function handleServerEvent(event) {
  if (event.type === "run.started") {
    addEvent({ node: "graph", detail: `Run ${event.run_id.slice(0, 7)} started`, status: "active" });
    return;
  }
  if (event.type === "graph.event") {
    applyGraphEvent(event);
    return;
  }
  if (event.type === "run.interrupted") {
    const question = event.question || "The graph needs more information.";
    state.messages.push({ role: "assistant", content: question });
    state.pendingResume = true;
    elements.interruptBanner.hidden = false;
    elements.composerHint.textContent = "Your response resumes Command(resume=…)";
    updateNode("support_agent", "waiting", question);
    addEvent({ node: "support_agent", detail: "Checkpoint saved; awaiting learner input", status: "waiting" });
    configureRunEnd("waiting");
    return;
  }
  if (event.type === "run.completed") {
    state.route = event.route || state.route;
    state.results = event.agent_results || [];
    state.messages.push({ role: "assistant", content: event.answer || "The graph completed without an answer." });
    state.pendingResume = false;
    elements.interruptBanner.hidden = true;
    elements.composerHint.textContent = "Enter to send · Shift + Enter for a new line";
    ["product_agent", "support_agent"].forEach((agent) => {
      if (!state.route.includes(agent)) updateNode(agent, "skipped");
    });
    updateStatePanel("saved");
    addEvent({ node: "graph", detail: "Run completed and checkpoint saved", status: "complete" });
    configureRunEnd("complete");
    return;
  }
  if (event.type === "run.error") showError(event.message || "Unknown graph error");
}

async function sendMessage(text) {
  if (!text.trim() || state.running) return;
  const content = text.trim();
  const wasResume = state.pendingResume;
  state.messages.push({ role: "user", content });
  elements.input.value = "";
  resizeInput();
  configureRunStart();

  const controller = new AbortController();
  state.controller = controller;
  const requestBody = {
    message: wasResume ? "" : content,
    resume: wasResume ? content : null,
    thread_id: state.threadId,
    model: getModel(),
    history: historyForApi().slice(0, -1),
  };
  const headers = { "Content-Type": "application/json" };
  const apiKey = getApiKey();
  if (apiKey) headers["X-OpenAI-API-Key"] = apiKey;

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers,
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `Request failed (${response.status})`);
    }
    await readStream(response);
  } catch (error) {
    if (error.name !== "AbortError") showError(error.message || "The Python API is unavailable.");
  }
}

function resizeInput() {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 150)}px`;
}

async function resetConversation() {
  state.controller?.abort();
  const previousThread = state.threadId;
  state.threadId = crypto.randomUUID();
  state.messages = [];
  state.events = [];
  state.route = [];
  state.results = [];
  state.pendingResume = false;
  state.running = false;
  elements.interruptBanner.hidden = true;
  elements.eventList.innerHTML = '<li class="event-empty">Run the graph to stream node and tool events here.</li>';
  elements.routeExplanation.textContent = "Send a message to see the orchestrator's typed routing decision.";
  resetNodes();
  setRunBadge("Ready");
  updateStatePanel("idle");
  renderMessages();
  fetch("/api/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: previousThread }),
  }).catch(() => {});
}

function switchTab(button) {
  document.querySelectorAll(".inspector-tabs button").forEach((tab) => tab.setAttribute("aria-selected", String(tab === button)));
  document.querySelectorAll(".tab-panel").forEach((panel) => { panel.hidden = panel.id !== `${button.dataset.tab}-panel`; });
}

function openSettings() {
  elements.apiKeyInput.value = getApiKey();
  elements.modelInput.value = getModel();
  elements.settingsDialog.showModal();
}

function saveSettings(event) {
  if (event.submitter?.value === "cancel") return;
  const apiKey = elements.apiKeyInput.value.trim();
  const model = elements.modelInput.value.trim() || "gpt-5.4-mini";
  if (apiKey) sessionStorage.setItem("axiomcart-openai-key", apiKey);
  else sessionStorage.removeItem("axiomcart-openai-key");
  localStorage.setItem("axiomcart-model", model);
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    if (!response.ok) throw new Error("Health check failed");
    const health = await response.json();
    state.serverKeyConfigured = health.server_key_configured;
    elements.serviceStatus.dataset.status = "ready";
    elements.serviceStatus.lastElementChild.textContent = "Python agent ready";
    elements.versionChip.textContent = `Python ${health.python} · LangGraph ${health.langgraph}`;
    elements.serverKeyNote.dataset.status = health.server_key_configured ? "ready" : "local";
    elements.serverKeyNote.lastElementChild.textContent = health.server_key_configured
      ? "This deployment has a server API key configured."
      : "No server key found. Add your own key above.";
  } catch {
    elements.serviceStatus.dataset.status = "error";
    elements.serviceStatus.lastElementChild.textContent = "Python API offline";
    elements.serverKeyNote.lastElementChild.textContent = "The Python API is not reachable.";
  }
}

elements.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(elements.input.value);
});
elements.input.addEventListener("input", resizeInput);
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.composer.requestSubmit();
  }
});
elements.promptStrip.addEventListener("click", (event) => {
  const prompt = event.target.closest("[data-prompt]")?.dataset.prompt;
  if (prompt) sendMessage(prompt);
});
elements.resetButton.addEventListener("click", resetConversation);
elements.settingsOpen.addEventListener("click", openSettings);
elements.settingsForm.addEventListener("submit", saveSettings);
elements.keyVisibility.addEventListener("click", () => {
  const show = elements.apiKeyInput.type === "password";
  elements.apiKeyInput.type = show ? "text" : "password";
  elements.keyVisibility.textContent = show ? "Hide" : "Show";
  elements.keyVisibility.setAttribute("aria-label", `${show ? "Hide" : "Show"} API key`);
});
document.querySelectorAll(".inspector-tabs button").forEach((button) => button.addEventListener("click", () => switchTab(button)));

renderWelcome();
updateStatePanel("idle");
loadHealth();
