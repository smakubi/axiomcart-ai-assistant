import { highlightPython } from "./python-highlight.js?v=20260802-8";

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
  latency: {
    input: document.querySelector("#latency-input"),
    transcription: document.querySelector("#latency-transcription"),
    graph: document.querySelector("#latency-graph"),
    speech: document.querySelector("#latency-speech"),
  },
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
  recordingStartedAt: null,
  shouldProcessRecording: false,
  voiceSessionActive: false,
  audioContext: null,
  audioSource: null,
  analyser: null,
  silenceFrame: null,
  speechDetected: false,
  silenceStartedAt: null,
  speechController: null,
  speechAudioContext: null,
  speechSources: new Set(),
  voiceReplies: true,
  runStartedAt: null,
  provider: "—",
  model: "—",
  architecture: null,
  timings: {},
};

const voiceStages = {
  idle: ["Voice input", "Start voice conversation", "Speak normally. It keeps listening until you end the conversation."],
  listening: ["Listening", "Speak naturally", "A short pause sends your turn. The microphone resumes after the answer."],
  transcribing: ["Transcribing", "Converting speech to text", "The transcript will be sent to the graph automatically."],
  thinking: ["Running", "Processing your request", "Follow the active nodes and events in the graph panel."],
  speaking: ["Speaking", "Playing the response", "Listening resumes automatically when playback finishes."],
  error: ["Voice unavailable", "Use the keyboard or try again", "Check microphone permission and speech configuration in Settings."],
};

const latencyStageForVoiceStage = {
  listening: "input",
  transcribing: "transcription",
  thinking: "graph",
  speaking: "speech",
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

function formatDuration(milliseconds) {
  if (!Number.isFinite(milliseconds)) return "—";
  return milliseconds < 1000 ? `${Math.round(milliseconds)} ms` : `${(milliseconds / 1000).toFixed(1)} s`;
}

function setTiming(stage, milliseconds) {
  state.timings[stage] = Math.round(milliseconds);
  elements.latency[stage].textContent = formatDuration(milliseconds);
  elements.latency[stage].closest("article").dataset.status = "complete";
}

function resetTimings() {
  state.timings = {};
  Object.entries(elements.latency).forEach(([stage, element]) => {
    element.textContent = "Ready";
    element.closest("article").dataset.status = "ready";
    element.closest("article").dataset.stage = stage;
  });
}

function setVoiceStage(stage, detail) {
  const [label, status, defaultDetail] = voiceStages[stage];
  elements.voiceConsole.dataset.stage = stage;
  elements.voiceStageLabel.textContent = label;
  elements.voiceStatus.textContent = status;
  elements.voiceDetail.textContent = detail || defaultDetail;
  elements.voiceConsole.dataset.session = state.voiceSessionActive ? "active" : "inactive";
  elements.voiceButton.setAttribute(
    "aria-label",
    state.voiceSessionActive ? "End voice conversation" : "Start voice conversation",
  );
  document.querySelectorAll("[data-latency-stage]").forEach((card) => {
    if (card.dataset.status !== "complete") card.dataset.status = "ready";
  });
  const activeLatencyStage = latencyStageForVoiceStage[stage];
  if (activeLatencyStage) {
    document.querySelector(`[data-latency-stage="${activeLatencyStage}"]`).dataset.status = "active";
  }
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
    card.querySelector(".node-latency").textContent = "—";
  });
}

function updateNode(node, status, detail = "", durationMs) {
  const card = document.querySelector(`[data-node="${node}"]`);
  if (card) {
    card.dataset.status = status;
    const statusLabel = { active: "Active", complete: "Done", waiting: "Paused", skipped: "Skipped", error: "Error", ready: "Ready" }[status] || status;
    card.querySelector(".node-status").textContent = statusLabel;
    if (Number.isFinite(durationMs)) {
      card.querySelector(".node-latency").textContent = formatDuration(durationMs);
    }
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
      <time>${Number.isFinite(item.elapsed_ms) ? `+${formatDuration(item.elapsed_ms)} · ` : ""}${Number.isFinite(item.duration_ms) ? `${formatDuration(item.duration_ms)} node · ` : ""}${item.at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time>
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
  updateStatePanel(status === "waiting" ? "interrupted" : status);
  renderMessages();
  if (!elements.textEntry.hidden) elements.input.focus();
}

function applyGraphEvent(event) {
  updateNode(event.node, event.status, event.detail, event.duration_ms);
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
  if (state.voiceSessionActive) {
    state.voiceSessionActive = false;
    stopPlayback();
    releaseMicrophone();
  }
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
    setTiming("graph", event.elapsed_ms || performance.now() - state.runStartedAt);
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
    setTiming("graph", event.elapsed_ms || performance.now() - state.runStartedAt);
    addEvent({
      node: "graph",
      detail: "Run completed and checkpoint saved",
      status: "complete",
      elapsed_ms: event.elapsed_ms,
    });
    configureRunEnd("complete");
    if (state.voiceReplies) speakText(answer);
    else resumeListening();
    return;
  }
  if (event.type === "run.error") showError(event.message || "Unknown graph error");
}

async function sendMessage(text, { voiceInput = false } = {}) {
  if (!text.trim() || state.running) return;
  if (state.mediaRecorder?.state === "recording") finishVoiceTurn(false);
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
  if (state.voiceSessionActive) endVoiceSession();
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
  resetTimings();
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

function clearTurnMonitoring() {
  if (state.silenceFrame) cancelAnimationFrame(state.silenceFrame);
  clearTimeout(state.recordingTimer);
  state.silenceFrame = null;
  state.recordingTimer = null;
  state.speechDetected = false;
  state.silenceStartedAt = null;
}

function releaseMicrophone() {
  clearTurnMonitoring();
  state.audioSource?.disconnect();
  state.audioContext?.close().catch(() => {});
  state.mediaStream?.getTracks().forEach((track) => track.stop());
  state.audioContext = null;
  state.audioSource = null;
  state.analyser = null;
  state.mediaStream = null;
}

function finishVoiceTurn(shouldProcess = true) {
  if (state.mediaRecorder?.state !== "recording") return;
  if (shouldProcess && state.recordingStartedAt) {
    setTiming("input", performance.now() - state.recordingStartedAt);
  }
  state.recordingStartedAt = null;
  state.shouldProcessRecording = shouldProcess;
  clearTurnMonitoring();
  state.mediaRecorder.stop();
}

function monitorSilence() {
  if (!state.analyser || state.mediaRecorder?.state !== "recording") return;
  const samples = new Uint8Array(state.analyser.fftSize);
  state.analyser.getByteTimeDomainData(samples);
  const volume = Math.sqrt(
    samples.reduce((sum, sample) => sum + ((sample - 128) / 128) ** 2, 0) / samples.length,
  );
  const now = performance.now();
  if (volume > 0.025) {
    if (!state.speechDetected) {
      resetTimings();
      state.recordingStartedAt = now;
    }
    state.speechDetected = true;
    state.silenceStartedAt = null;
  } else if (state.speechDetected) {
    state.silenceStartedAt ??= now;
    if (now - state.silenceStartedAt > 850) {
      finishVoiceTurn(true);
      return;
    }
  }
  state.silenceFrame = requestAnimationFrame(monitorSilence);
}

function beginListening() {
  const stream = state.mediaStream;
  if (!state.voiceSessionActive || !stream?.active || state.running) return;
  state.recordingChunks = [];
  state.shouldProcessRecording = false;
  state.recordingStartedAt = null;
  state.speechDetected = false;
  state.silenceStartedAt = null;
  const mimeType = preferredRecordingType();
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  state.mediaRecorder = recorder;
  recorder.addEventListener("dataavailable", (event) => {
    if (event.data.size) state.recordingChunks.push(event.data);
  });
  recorder.addEventListener("stop", () => {
    const shouldProcess = state.shouldProcessRecording;
    const blob = new Blob(state.recordingChunks, { type: recorder.mimeType || "audio/webm" });
    state.mediaRecorder = null;
    state.recordingChunks = [];
    state.shouldProcessRecording = false;
    if (shouldProcess && blob.size) transcribeRecording(blob);
    else if (state.voiceSessionActive && !state.running) beginListening();
  });
  recorder.start();
  state.recordingTimer = setTimeout(() => finishVoiceTurn(state.speechDetected), 30_000);
  setVoiceStage("listening");
  if (state.analyser) monitorSilence();
}

function resumeListening() {
  if (!state.voiceSessionActive) {
    setVoiceStage("idle");
    return;
  }
  setTimeout(beginListening, 180);
}

function endVoiceSession(detail = "Voice conversation ended. Press to start again.") {
  state.voiceSessionActive = false;
  if (state.mediaRecorder?.state === "recording") finishVoiceTurn(false);
  stopPlayback();
  releaseMicrophone();
  setVoiceStage("idle", detail);
}

function stopPlayback() {
  state.speechController?.abort();
  state.speechController = null;
  state.speechSources.forEach((source) => {
    try { source.stop(); } catch {}
  });
  state.speechSources.clear();
  state.speechAudioContext?.close().catch(() => {});
  state.speechAudioContext = null;
}

function voiceHeaders() {
  const apiKey = getApiKey();
  return apiKey ? { "X-OpenAI-API-Key": apiKey } : {};
}

async function transcribeRecording(blob) {
  setVoiceStage("transcribing");
  const startedAt = performance.now();
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
    const { text, latency_ms: serverLatency } = await response.json();
    setTiming("transcription", serverLatency || performance.now() - startedAt);
    if (!text?.trim()) {
      resumeListening();
      return;
    }
    await sendMessage(text, { voiceInput: true });
  } catch (error) {
    state.voiceSessionActive = false;
    releaseMicrophone();
    setVoiceStage("error", error.message || "The recording could not be transcribed.");
  }
}

async function startVoiceSession() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    setVoiceStage("error", "This browser does not support microphone recording.");
    return;
  }
  stopPlayback();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.mediaStream = stream;
    state.voiceSessionActive = true;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {
      state.audioContext = new AudioContext();
      state.analyser = state.audioContext.createAnalyser();
      state.analyser.fftSize = 1024;
      state.audioSource = state.audioContext.createMediaStreamSource(stream);
      state.audioSource.connect(state.analyser);
    }
    beginListening();
  } catch (error) {
    state.voiceSessionActive = false;
    setVoiceStage("error", error.name === "NotAllowedError" ? "Microphone permission was denied." : "The microphone could not be started.");
  }
}

function pcmSamples(chunk, trailingByte) {
  let bytes = chunk;
  if (trailingByte !== null) {
    bytes = new Uint8Array(chunk.byteLength + 1);
    bytes[0] = trailingByte;
    bytes.set(chunk, 1);
  }
  const usableLength = bytes.byteLength - (bytes.byteLength % 2);
  const view = new DataView(bytes.buffer, bytes.byteOffset, usableLength);
  const samples = new Float32Array(usableLength / 2);
  for (let index = 0; index < samples.length; index += 1) {
    samples[index] = view.getInt16(index * 2, true) / 32_768;
  }
  return {
    samples,
    trailingByte: usableLength < bytes.byteLength ? bytes[bytes.byteLength - 1] : null,
  };
}

function appendPcmBytes(current, incoming) {
  if (!current.byteLength) return incoming;
  const combined = new Uint8Array(current.byteLength + incoming.byteLength);
  combined.set(current);
  combined.set(incoming, current.byteLength);
  return combined;
}

async function playStreamingSpeech(response, startedAt, controller) {
  if (!response.body) throw new Error("Streaming speech is unavailable in this browser.");
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) throw new Error("Natural voice playback is unavailable in this browser.");

  const sampleRate = Number(response.headers.get("X-Audio-Sample-Rate")) || 24_000;
  const context = new AudioContext({ sampleRate });
  state.speechAudioContext = context;
  if (context.state === "suspended") await context.resume();

  const reader = response.body.getReader();
  const initialBufferBytes = sampleRate;
  let nextStartTime = context.currentTime;
  let pendingBytes = new Uint8Array();
  let trailingByte = null;
  let playbackScheduled = false;
  let streamComplete = false;
  let finished = false;

  const finish = () => {
    if (finished || !streamComplete || state.speechSources.size) return;
    finished = true;
    if (state.speechAudioContext === context) state.speechAudioContext = null;
    context.close().catch(() => {});
    resumeListening();
  };

  const scheduleChunk = (value) => {
    const decoded = pcmSamples(value, trailingByte);
    trailingByte = decoded.trailingByte;
    if (!decoded.samples.length) return;

    const buffer = context.createBuffer(1, decoded.samples.length, sampleRate);
    buffer.copyToChannel(decoded.samples, 0);
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    state.speechSources.add(source);
    source.onended = () => {
      state.speechSources.delete(source);
      finish();
    };
    const leadSeconds = playbackScheduled ? 0.04 : 0.12;
    nextStartTime = Math.max(nextStartTime, context.currentTime + leadSeconds);
    source.start(nextStartTime);
    if (!playbackScheduled) {
      playbackScheduled = true;
      setTiming(
        "speech",
        performance.now() - startedAt + (nextStartTime - context.currentTime) * 1000,
      );
    }
    nextStartTime += buffer.duration;
  };

  while (!controller.signal.aborted) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!playbackScheduled) {
      pendingBytes = appendPcmBytes(pendingBytes, value);
      if (pendingBytes.byteLength < initialBufferBytes) continue;
      scheduleChunk(pendingBytes);
      pendingBytes = new Uint8Array();
    } else {
      scheduleChunk(value);
    }
  }

  if (!controller.signal.aborted && pendingBytes.byteLength) scheduleChunk(pendingBytes);

  streamComplete = true;
  finish();
}

async function speakHostedText(text, startedAt) {
  const controller = new AbortController();
  state.speechController = controller;
  try {
    const response = await fetch("/api/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...voiceHeaders() },
      body: JSON.stringify({ text }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("Natural speech service unavailable");
    await playStreamingSpeech(response, startedAt, controller);
  } catch (error) {
    if (!controller.signal.aborted) {
      setVoiceStage("error", error.message || "Natural voice playback is unavailable.");
      resumeListening();
    }
  } finally {
    if (state.speechController === controller) state.speechController = null;
  }
}

function speakText(text) {
  stopPlayback();
  setVoiceStage("speaking", "Streaming a natural voice response.");
  speakHostedText(text, performance.now());
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
    elements.codeDialogSource.innerHTML = highlightPython(component.source);
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
  if (state.voiceSessionActive) endVoiceSession();
  else if (!state.running) startVoiceSession();
});
elements.voiceReplyToggle.addEventListener("click", () => {
  state.voiceReplies = !state.voiceReplies;
  elements.voiceReplyToggle.setAttribute("aria-pressed", String(state.voiceReplies));
  elements.voiceReplyToggle.querySelector("span").textContent = `Voice replies ${state.voiceReplies ? "on" : "off"}`;
  if (!state.voiceReplies) {
    stopPlayback();
    resumeListening();
  }
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
document.querySelectorAll(".concept-card[data-component]").forEach((card) => {
  card.addEventListener("click", () => openNodeSource(card.dataset.component));
});
elements.codeDialogClose.addEventListener("click", () => elements.codeDialog.close());
window.addEventListener("beforeunload", releaseMicrophone);

renderWelcome();
updateStatePanel("idle");
resetTimings();
setVoiceStage("idle");
loadHealth();
