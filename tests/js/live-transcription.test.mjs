import test from 'node:test';
import assert from 'node:assert/strict';
import { TurnDetector, TranscriptTurn } from '../../public/assets/live-transcription.mjs';

test('short pauses do not commit; 500 ms silence commits once', () => {
  const detector = new TurnDetector();
  assert.equal(detector.update(0.08, 100), false);
  assert.equal(detector.update(0, 450), false);
  assert.equal(detector.update(0.08, 460), false);
  assert.equal(detector.update(0, 959), false);
  assert.equal(detector.update(0, 960), true);
  assert.equal(detector.update(0, 1000), false);
  assert.equal(detector.lastSpeechAt, 460);
});

test('silence alone never produces a turn', () => {
  const detector = new TurnDetector();
  assert.equal(detector.update(0, 100000), false);
});

test('only the committed item can dispatch final text; duplicates are ignored', () => {
  const turn = new TranscriptTurn();
  turn.commit();
  assert.equal(turn.handle({type: 'input_audio_buffer.committed', item_id: 'one'}), null);
  assert.equal(turn.handle({type: 'conversation.item.input_audio_transcription.completed', item_id: 'old', transcript: 'stale'}), null);
  assert.equal(turn.handle({type: 'conversation.item.input_audio_transcription.completed', item_id: 'one', transcript: 'ORD102'}), 'ORD102');
  assert.equal(turn.handle({type: 'conversation.item.input_audio_transcription.completed', item_id: 'one', transcript: 'ORD102'}), null);
});

test('deltas are preview only; clear cancels a pending turn', () => {
  const turn = new TranscriptTurn();
  assert.equal(turn.handle({type: 'conversation.item.input_audio_transcription.delta', item_id: 'one', delta: 'Where is'}), null);
  assert.equal(turn.preview, 'Where is');
  turn.commit();
  turn.clear();
  assert.equal(turn.handle({type: 'input_audio_buffer.committed', item_id: 'one'}), null);
  assert.equal(turn.handle({type: 'conversation.item.input_audio_transcription.completed', item_id: 'one', transcript: 'Where is my order?'}), null);
});

// Real connect/pause lifecycle, with only browser hardware and provider I/O stubbed.
// Connection setup must never override the app's pause during a concurrent graph run.
test('a completed connection stays muted until the app explicitly starts listening', async (t) => {
  const { LiveTranscription } = await import('../../public/assets/live-transcription.mjs');
  const track = { enabled: true };
  const channel = { readyState: 'open', addEventListener() {}, send() {}, close() {} };
  class Peer {
    addTrack() {}
    createDataChannel() { return channel; }
    addEventListener() {}
    async createOffer() { return { sdp: 'offer' }; }
    async setLocalDescription() {}
    async setRemoteDescription() {}
    close() {}
  }
  class Audio {
    async resume() {}
    createAnalyser() { return { fftSize: 0, getByteTimeDomainData(samples) { samples.fill(128); } }; }
    createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
    async close() {}
  }
  const previous = { window: globalThis.window, RTCPeerConnection: globalThis.RTCPeerConnection,
    requestAnimationFrame: globalThis.requestAnimationFrame, cancelAnimationFrame: globalThis.cancelAnimationFrame };
  Object.assign(globalThis, { window: { AudioContext: Audio }, RTCPeerConnection: Peer,
    requestAnimationFrame: () => 1, cancelAnimationFrame() {} });
  t.after(() => Object.assign(globalThis, previous));
  t.mock.method(globalThis, 'fetch', async (url) => url === '/api/voice/session'
    ? { ok: true, async json() { return { value: 'ephemeral-test' }; } }
    : { ok: true, async text() { return 'answer'; } });
  const live = new LiveTranscription({ headers: () => ({}), onPreview() {}, onListening() {},
    onCommit() {}, onTranscript() {}, onError() {} });
  await live.connect({ getAudioTracks: () => [track] });
  assert.equal(live.listening, false);
  assert.equal(track.enabled, false);
  live.resume();
  assert.equal(live.listening, true);
  live.close();
  assert.equal(track.enabled, false);
});
