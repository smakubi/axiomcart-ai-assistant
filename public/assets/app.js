const elements = {
  serviceStatus: document.querySelector("#service-status"),
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
  stateProvider: document.querySelector("#state-provider"),
  stateModel: document.querySelector("#state-model"),
  stateElapsed: document.querySelector("#state-elapsed"),
  voiceConsole: document.querySelector("#voice-console"),
  voiceButton: document.querySelector("#voice-button"),
  voiceStageLabel: document.querySelector("#voice-stage-label"),
  voiceStatus: document.querySelector("#voice-status"),
  voiceDetail: document.querySelector("#voice-detail"),
  voiceReplyToggle: document.querySelector("#voice-reply-toggle"),
  keyboardToggle: document.querySelector("#keyboard-toggle"),
  textEntry: document.querySelector("#text-entry"),
  settingsDialog: document.querySelector("#settings-dialog"),
  settingsOpen: document.querySelector("#settings-open"),
  settingsForm: document.querySelector("#settings-form"),
  settingsSave: document.querySelector("#settings-save"),
  apiKeyInput: document.querySelector("#api-key-input"),
  modelInput: document.querySelector("#model-input"),
  keyVisibility: document.querySelector("#key-visibility"),
  serverKeyNote: document.querySelector("#server-key-note"),
  codeDialog: document.querySelector("#code-dialog"),
  codeDialogClose: document.querySelector("#code-dialog-close"),
  codeDialogTitle: document.querySelector("#code-dialog-title"),
  codeDialogPath: document.querySelector("#code-dialog-path"),
  codeDialogRole: document.querySelector("#code-dialog-role"),
  codeDialogSource: document.querySelector("#code-dialog-source"),
  architectureLink: document.querySelector("#architecture-link"),
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
  mediaRecorder: null,
  mediaStream: null,
  recordingChunks: [],
  recordingTimer: null,
  responseAudio: null,
  voiceReplies: true,
  runStartedAt: null,
  provider: "—",
  model: "—",
  architecture: null,
};

const voiceStages = {
  idle: ["Ready", "Press the microphone to speak", "Audio is transcribed, processed by the graph, and returned as speech."],
  listening: ["Listening", "Speak naturally", "Press the microphone again when you are finished."],
  transcribing: ["Transcribing", "Converting speech to text", "The transcript will be sent to the graph automatically."],
  thinking: ["Running", "Processing your request", "Follow the active nodes and events in the graph panel."],
  speaking: ["Speaking", "Playing the response", "You can stop playback or begin another turn when it finishes."],
  error: ["Voice unavailable", "Use the keyboard or try again", "Check microphone permission and speech configuration in Settings."],
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

function setVoiceStage(stage, detail) {
  const [label, status, defaultDetail] = voiceStages[stage];
  elements.voiceConsole.dataset.stage = stage;
  elements.voiceStageLabel.textContent = label;
  elements.voiceStatus.textContent = status;
  elements.voiceDetail.textContent = detail || defaultDetail;
  elements.voiceButton.setAttribute("aria-label", stage === "listening" ? "Stop recording" : "Start recording");
}

function renderWelcome() {
  elements.transcript.innerHTML = `
    <div class="welcome-state">
      <div>
        <span class="welcome-orb" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M4 7h16l-2 11H6L4 7Zm3 0a5 5 0 0 1 10 0M9 21h.01M15 21h.01" /></svg>
        </span>
        <h3>Start with your voice</h3>
        <p>Press the microphone above and ask about a product or an order. Keyboard input remains available below.</p>
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
  elements.stateProvider.textContent = state.provider;
  elements.stateModel.textContent = state.model;
  elements.stateElapsed.textContent = state.runStartedAt
    ? `${Math.round(performance.now() - state.runStartedAt)} ms`
    : "—";
}

function configureRunStart() {
  state.running = true;
  state.events = [];
  state.route = [];
  state.results = [];
  state.runStartedAt = performance.now();
  resetNodes();
  updateNode("orchestrator", "active");
  setRunBadge("Running", "running");
  setVoiceStage("thinking");
  elements.sendButton.disabled = true;
  elements.voiceButton.disabled = true;
  elements.promptStrip.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  elements.eventList.innerHTML = "";
  updateStatePanel("running");
  renderMessages();
}

function configureRunEnd(status = "complete") {
  state.running = false;
  state.controller = null;
  elements.sendButton.disabled = false;
  elements.voiceButton.disabled = false;
  elements.promptStrip.querySelectorAll("button").forEach((button) => { button.disabled = false; });
  setRunBadge(status === "complete" ? "Complete" : status === "waiting" ? "Paused" : "Error", status);
  updateStatePanel(status === "waiting" ? "interrupted" : status);
  renderMessages();
  if (!elements.textEntry.hidden) elements.input.focus();
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
  setVoiceStage("error", message);
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
    state.provider = event.provider || "—";
    state.model = event.model || "—";
    updateStatePanel("running");
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
    if (state.voiceReplies) speakText(question);
    return;
  }
  if (event.type === "run.completed") {
    state.route = event.route || state.route;
    state.results = event.agent_results || [];
    const answer = event.answer || "The graph completed without an answer.";
    state.messages.push({ role: "assistant", content: answer });
    state.pendingResume = false;
    elements.interruptBanner.hidden = true;
    elements.composerHint.textContent = "Enter to send · Shift + Enter for a new line";
    ["product_agent", "support_agent"].forEach((agent) => {
      if (!state.route.includes(agent)) updateNode(agent, "skipped");
    });
    updateStatePanel("saved");
    addEvent({ node: "graph", detail: "Run completed and checkpoint saved", status: "complete" });
    configureRunEnd("complete");
    if (state.voiceReplies) speakText(answer);
    else setVoiceStage("idle");
    return;
  }
  if (event.type === "run.error") showError(event.message || "Unknown graph error");
}

async function sendMessage(text, { voiceInput = false } = {}) {
  if (!text.trim() || state.running) return;
  const content = text.trim();
  const wasResume = state.pendingResume;
  state.messages.push({ role: "user", content });
  elements.input.value = "";
  resizeInput();
  configureRunStart();
  if (voiceInput) setVoiceStage("thinking");

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
  state.runStartedAt = null;
  state.provider = "—";
  state.model = "—";
  elements.interruptBanner.hidden = true;
  elements.eventList.innerHTML = '<li class="event-empty">Run the graph to stream node and tool events here.</li>';
  elements.routeExplanation.textContent = "Routing details appear after the first message.";
  resetNodes();
  setRunBadge("Ready");
  stopPlayback();
  setVoiceStage("idle");
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

function toggleKeyboard() {
  const willOpen = elements.textEntry.hidden;
  elements.textEntry.hidden = !willOpen;
  elements.keyboardToggle.setAttribute("aria-expanded", String(willOpen));
  elements.keyboardToggle.querySelector("span").textContent = willOpen ? "Hide keyboard" : "Use keyboard";
  if (willOpen) elements.input.focus();
}

function preferredRecordingType() {
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function stopPlayback() {
  if (state.responseAudio) {
    state.responseAudio.pause();
    state.responseAudio = null;
  }
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

function voiceHeaders() {
  const apiKey = getApiKey();
  return apiKey ? { "X-OpenAI-API-Key": apiKey } : {};
}

async function transcribeRecording(blob) {
  setVoiceStage("transcribing");
  const formData = new FormData();
  const extension = blob.type.includes("mp4") ? "m4a" : "webm";
  formData.append("audio", blob, `recording.${extension}`);
  try {
    const response = await fetch("/api/voice/transcribe", {
      method: "POST",
      headers: voiceHeaders(),
      body: formData,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `Transcription failed (${response.status})`);
    }
    const { text } = await response.json();
    if (!text?.trim()) throw new Error("No speech was detected.");
    await sendMessage(text, { voiceInput: true });
  } catch (error) {
    setVoiceStage("error", error.message || "The recording could not be transcribed.");
  }
}

function stopRecording() {
  if (state.mediaRecorder?.state === "recording") state.mediaRecorder.stop();
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    setVoiceStage("error", "This browser does not support microphone recording.");
    return;
  }
  stopPlayback();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = preferredRecordingType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    state.mediaStream = stream;
    state.mediaRecorder = recorder;
    state.recordingChunks = [];
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size) state.recordingChunks.push(event.data);
    });
    recorder.addEventListener("stop", () => {
      clearTimeout(state.recordingTimer);
      state.mediaStream?.getTracks().forEach((track) => track.stop());
      const blob = new Blob(state.recordingChunks, { type: recorder.mimeType || "audio/webm" });
      state.mediaRecorder = null;
      state.mediaStream = null;
      state.recordingChunks = [];
      transcribeRecording(blob);
    });
    recorder.start();
    state.recordingTimer = setTimeout(stopRecording, 30_000);
    setVoiceStage("listening");
  } catch (error) {
    setVoiceStage("error", error.name === "NotAllowedError" ? "Microphone permission was denied." : "The microphone could not be started.");
  }
}

function browserSpeak(text) {
  if (!("speechSynthesis" in window)) {
    setVoiceStage("error", "Audio playback is unavailable in this browser.");
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.02;
  utterance.onend = () => setVoiceStage("idle");
  utterance.onerror = () => setVoiceStage("idle");
  window.speechSynthesis.speak(utterance);
}

async function speakText(text) {
  stopPlayback();
  setVoiceStage("speaking");
  let audioUrl = null;
  try {
    const response = await fetch("/api/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...voiceHeaders() },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error("Speech service unavailable");
    audioUrl = URL.createObjectURL(await response.blob());
    const audio = new Audio(audioUrl);
    state.responseAudio = audio;
    const finish = () => {
      URL.revokeObjectURL(audioUrl);
      if (state.responseAudio === audio) state.responseAudio = null;
      setVoiceStage("idle");
    };
    audio.onended = finish;
    audio.onerror = () => {
      finish();
      browserSpeak(text);
    };
    await audio.play();
  } catch {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    state.responseAudio = null;
    browserSpeak(text);
  }
}

async function loadArchitecture() {
  if (state.architecture) return state.architecture;
  const response = await fetch("/api/architecture", { cache: "no-store" });
  if (!response.ok) throw new Error("Architecture source is unavailable.");
  state.architecture = await response.json();
  return state.architecture;
}

async function openNodeSource(nodeId) {
  try {
    const architecture = await loadArchitecture();
    const component = architecture.components.find((item) => item.id === nodeId);
    if (!component) return;
    elements.codeDialogTitle.textContent = component.title;
    elements.codeDialogPath.textContent = component.path;
    elements.codeDialogRole.textContent = component.role;
    elements.codeDialogSource.textContent = component.source;
    elements.architectureLink.href = `/architecture#${component.id}`;
    elements.codeDialog.showModal();
  } catch (error) {
    elements.routeExplanation.textContent = error.message;
  }
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
    state.provider = health.provider || "—";
    state.model = health.model || "—";
    elements.serviceStatus.dataset.status = "ready";
    elements.serviceStatus.lastElementChild.textContent = health.provider ? `${health.provider} ready` : "API ready";
    elements.serverKeyNote.dataset.status = health.server_key_configured ? "ready" : "local";
    elements.serverKeyNote.lastElementChild.textContent = health.server_key_configured
      ? `${health.model} is configured on ${health.provider}. Speech ${health.speech_configured ? "is ready" : "needs an OpenAI key"}.`
      : "No server model found. Add your own OpenAI key above.";
    updateStatePanel("idle");
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
elements.voiceButton.addEventListener("click", () => {
  if (state.mediaRecorder?.state === "recording") stopRecording();
  else if (!state.running) startRecording();
});
elements.voiceReplyToggle.addEventListener("click", () => {
  state.voiceReplies = !state.voiceReplies;
  elements.voiceReplyToggle.setAttribute("aria-pressed", String(state.voiceReplies));
  elements.voiceReplyToggle.querySelector("span").textContent = `Voice replies ${state.voiceReplies ? "on" : "off"}`;
  if (!state.voiceReplies) stopPlayback();
});
elements.keyboardToggle.addEventListener("click", toggleKeyboard);
elements.settingsOpen.addEventListener("click", openSettings);
elements.settingsForm.addEventListener("submit", saveSettings);
elements.keyVisibility.addEventListener("click", () => {
  const show = elements.apiKeyInput.type === "password";
  elements.apiKeyInput.type = show ? "text" : "password";
  elements.keyVisibility.textContent = show ? "Hide" : "Show";
  elements.keyVisibility.setAttribute("aria-label", `${show ? "Hide" : "Show"} API key`);
});
document.querySelectorAll(".inspector-tabs button").forEach((button) => button.addEventListener("click", () => switchTab(button)));
document.querySelectorAll(".node-card[data-node]").forEach((card) => {
  card.addEventListener("click", () => openNodeSource(card.dataset.node));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openNodeSource(card.dataset.node);
    }
  });
});
elements.codeDialogClose.addEventListener("click", () => elements.codeDialog.close());

renderWelcome();
updateStatePanel("idle");
setVoiceStage("idle");
loadHealth();
