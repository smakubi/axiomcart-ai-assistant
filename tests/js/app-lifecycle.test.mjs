import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';

function loadApp(getUserMedia, options = {}) {
  // Stub DOM/hardware, but execute the deployed app's real lifecycle functions.
  const element = { style: {}, dataset: {}, value: '', textContent: '', hidden: true,
    classList: { add() {}, remove() {} }, addEventListener() {}, setAttribute() {},
    querySelectorAll: () => [], focus() {}, insertAdjacentHTML() {}, scrollIntoView() {} };
  element.querySelector = element.closest = () => element;
  element.lastElementChild = element;
  const document = { querySelector: () => element, querySelectorAll: () => [], addEventListener() {} };
  const context = vm.createContext({ document, navigator: { mediaDevices: { getUserMedia } },
    window: { MediaRecorder: class {}, RTCPeerConnection: class {}, addEventListener() {} },
    localStorage: { getItem: () => null }, sessionStorage: { getItem: () => null },
    crypto: webcrypto, AbortController, performance, setTimeout, clearTimeout, TextDecoder,
    cancelAnimationFrame() {}, fetch: async () => ({ ok: false }),
    LiveTranscription: class { close() {} async connect() {} }, highlightPython: x => x,
    ...options });
  const source = readFileSync(new URL('../../public/assets/app.js', import.meta.url), 'utf8')
    .replace(/^import .*;\n/gm, '');
  vm.runInContext(source + '\n globalThis.app = {state, resetConversation, startVoiceSession, readStream, sendMessage, beginListening, speakHostedText};', context);
  return context.app;
}

test('reset during microphone permission cancels startup and stops the late microphone', async () => {
  let resolveMicrophone;
  const app = loadApp(() => new Promise(resolve => { resolveMicrophone = resolve; }));
  const start = app.startVoiceSession();
  assert.equal(app.state.voiceConnecting, true);
  await app.resetConversation();
  let stopped = false;
  resolveMicrophone({ getTracks: () => [{ stop() { stopped = true; } }] });
  await start;
  assert.equal(stopped, true);
  assert.equal(app.state.voiceSessionActive, false);
  assert.equal(app.state.liveTranscription, null);
});

function eventResponse(events) {
  let sent = false;
  return { ok: true, body: { getReader: () => ({
    async read() {
      if (sent) return { done: true };
      sent = true;
      return { value: new TextEncoder().encode(events.map(JSON.stringify).join('\n') + '\n'), done: false };
    },
  }) } };
}

test('an interrupted graph stream releases the UI rather than freezing Running', async () => {
  const app = loadApp(null, { fetch: async () => eventResponse([
    { type: 'run.started', run_id: 'interrupted' },
  ]) });
  await app.sendMessage('hello');
  assert.equal(app.state.running, false);
  assert.match(app.state.messages.at(-1).content, /ended before/i);
});

test('a stalled request times out and releases the UI', async () => {
  let timeout;
  const app = loadApp(null, {
    setTimeout(fn, ms) { if (ms === 60_000) timeout = fn; return 1; },
    clearTimeout() {},
    fetch: (_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    }),
  });
  const request = app.sendMessage('hello');
  assert.equal(app.state.running, true);
  assert.equal(typeof timeout, 'function');
  timeout();
  await request;
  assert.equal(app.state.running, false);
  assert.match(app.state.messages.at(-1).content, /timed out/i);
});

test('a stalled speech request closes playback and releases its controller', async () => {
  let timeout;
  const app = loadApp(null, {
    setTimeout(fn, ms) { if (ms === 30_000) timeout = fn; return 1; },
    clearTimeout() {},
    fetch: (_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    }),
  });
  let closed = false;
  app.state.speechAudioContext = { close: async () => { closed = true; } };
  const speech = app.speakHostedText('Hello', performance.now());
  timeout();
  await speech;
  assert.equal(closed, true);
  assert.equal(app.state.speechAudioContext, null);
  assert.equal(app.state.speechController, null);
});

test('listening cannot resume while answer audio is still playing', () => {
  const app = loadApp(null);
  app.state.voiceSessionActive = true;
  app.state.mediaStream = { active: true };
  let resumed = false;
  app.state.liveTranscription = { resume() { resumed = true; } };
  app.state.speechSources.add({});
  app.beginListening();
  assert.equal(resumed, false);
});
