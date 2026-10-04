import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';

function loadApp(getUserMedia) {
  // Stub DOM/hardware, but execute the deployed app's real lifecycle functions.
  const element = { style: {}, dataset: {}, value: '', textContent: '', hidden: true,
    classList: { add() {}, remove() {} }, addEventListener() {}, setAttribute() {},
    querySelectorAll: () => [], focus() {} };
  element.querySelector = element.closest = () => element;
  element.lastElementChild = element;
  const document = { querySelector: () => element, querySelectorAll: () => [], addEventListener() {} };
  const context = vm.createContext({ document, navigator: { mediaDevices: { getUserMedia } },
    window: { MediaRecorder: class {}, RTCPeerConnection: class {}, addEventListener() {} },
    localStorage: { getItem: () => null }, sessionStorage: { getItem: () => null },
    crypto: webcrypto, AbortController, performance, setTimeout, clearTimeout,
    cancelAnimationFrame() {}, fetch: async () => ({ ok: false }),
    LiveTranscription: class { close() {} async connect() {} }, highlightPython: x => x });
  const source = readFileSync(new URL('../../public/assets/app.js', import.meta.url), 'utf8')
    .replace(/^import .*;\n/gm, '');
  vm.runInContext(source + '\n globalThis.app = {state, resetConversation, startVoiceSession};', context);
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
