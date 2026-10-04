// Transcription only: finalized text goes to LangGraph; speech comes from TTS.
export class TurnDetector {
  constructor({ silenceMs = 500, threshold = 0.025, maxTurnMs = 30000 } = {}) {
    Object.assign(this, { silenceMs, threshold, maxTurnMs });
    this.reset();
  }
  reset() { this.startedAt = null; this.lastSpeechAt = null; this.committed = false; }
  update(volume, now) {
    if (this.committed) return false;
    if (volume > this.threshold) {
      this.startedAt ??= now;
      this.lastSpeechAt = now;
    }
    if (this.startedAt === null) return false;
    if (now - this.lastSpeechAt >= this.silenceMs || now - this.startedAt >= this.maxTurnMs) {
      this.committed = true;
      return true;
    }
    return false;
  }
}

// Deltas are captions, never executable customer requests. Match final events
// to the item acknowledged by commit so old/duplicate events cannot run a graph.
export class TranscriptTurn {
  constructor() { this.clear(); }
  clear() { this.pending = false; this.itemId = null; this.preview = ''; this.parts = new Map(); }
  commit() { this.pending = true; }
  handle(event) {
    if (event.type === 'input_audio_buffer.committed' && this.pending && !this.itemId) {
      this.itemId = event.item_id;
    }
    if (event.type === 'conversation.item.input_audio_transcription.delta') {
      this.parts.set(event.item_id, (this.parts.get(event.item_id) || '') + event.delta);
      this.preview = this.parts.get(event.item_id);
    }
    if (event.type !== 'conversation.item.input_audio_transcription.completed'
        || !this.pending || event.item_id !== this.itemId) return null;
    const text = event.transcript.trim();
    this.clear();
    return text;
  }
}

export class LiveTranscription {
  constructor({ headers, onPreview, onListening, onCommit, onTranscript, onError }) {
    Object.assign(this, { headers, onPreview, onListening, onCommit, onTranscript, onError });
    this.turn = new TranscriptTurn();
    this.detector = new TurnDetector();
    this.closed = false;
    this.listening = false;
    this.controller = new AbortController();
  }
  async connect(stream) {
    this.stream = stream;
    this.pause();
    this.pc = new RTCPeerConnection();
    this.pc.addTrack(stream.getAudioTracks()[0], stream);
    this.channel = this.pc.createDataChannel('oai-events');
    this.channel.addEventListener('message', ({ data }) => {
      if (this.closed) return;
      try { this.handleEvent(JSON.parse(data)); }
      catch { this.fail('The transcription connection returned an invalid event.'); }
    });
    this.channel.addEventListener('close', () => {
      if (!this.closed) this.fail('The transcription connection closed. Start voice again.');
    });
    this.pc.addEventListener('connectionstatechange', () => {
      if (this.pc.connectionState === 'failed') this.fail('The microphone connection failed.');
    });
    const tokenResponse = await fetch('/api/voice/session', {
      method: 'POST', headers: this.headers(), signal: this.controller.signal,
    });
    if (!tokenResponse.ok) {
      const payload = await tokenResponse.json().catch(() => ({}));
      throw new Error(payload.detail || 'Live transcription is unavailable.');
    }
    const { value } = await tokenResponse.json();
    if (this.closed) return;
    const offer = await this.pc.createOffer();
    await this.pc.setLocalDescription(offer);
    const response = await fetch('https://api.openai.com/v1/realtime/calls', {
      method: 'POST', body: offer.sdp,
      headers: { Authorization: `Bearer ${value}`, 'Content-Type': 'application/sdp' },
      signal: this.controller.signal,
    });
    if (!response.ok) throw new Error('Live transcription could not connect.');
    if (this.closed) return;
    await this.pc.setRemoteDescription({ type: 'answer', sdp: await response.text() });
    if (this.channel.readyState !== 'open') {
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('Transcription connection timed out.')), 15000);
        const finish = (callback, value) => { clearTimeout(timer); callback(value); };
        this.channel.addEventListener('open', () => finish(resolve), { once: true });
        this.channel.addEventListener('close', () => finish(reject, new Error('Connection closed.')), { once: true });
      });
    }
    if (this.closed) return;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    this.context = new AudioContext();
    await this.context.resume();
    if (this.closed) {
      await this.context.close();
      return;
    }
    this.analyser = this.context.createAnalyser();
    this.analyser.fftSize = 1024;
    this.source = this.context.createMediaStreamSource(stream);
    this.source.connect(this.analyser);
    // The application starts listening explicitly. A graph/TTS request may
    // have paused the microphone while connection setup was in flight.
  }
  send(event) {
    if (this.channel?.readyState === 'open') this.channel.send(JSON.stringify(event));
  }
  handleEvent(event) {
    if (this.closed) return;
    if (event.type === 'error' || event.type === 'conversation.item.input_audio_transcription.failed') {
      this.fail('Live transcription failed. Start voice again or use the keyboard.');
      return;
    }
    // Ignore captions while processing/playing except for the turn awaiting final text.
    if (!this.listening && !this.turn.pending) return;
    const text = this.turn.handle(event);
    if (event.type === 'conversation.item.input_audio_transcription.delta') this.onPreview(this.turn.preview);
    if (text !== null) {
      clearTimeout(this.finalTimer);
      this.onPreview('');
      this.onTranscript(text, performance.now() - this.committedAt);
    }
  }
  monitor() {
    if (!this.listening || this.closed) return;
    const samples = new Uint8Array(this.analyser.fftSize);
    this.analyser.getByteTimeDomainData(samples);
    const volume = Math.sqrt(samples.reduce((sum, x) => sum + ((x - 128) / 128) ** 2, 0) / samples.length);
    const now = performance.now();
    if (this.detector.update(volume, now)) {
      this.pause();
      this.turn.commit();
      this.committedAt = now;
      this.onCommit(now - this.detector.lastSpeechAt, this.detector.lastSpeechAt);
      this.send({ type: 'input_audio_buffer.commit' });
      this.finalTimer = setTimeout(() => this.fail('The final transcript timed out. Start voice again.'), 15000);
      return;
    }
    this.frame = requestAnimationFrame(() => this.monitor());
  }
  pause({ discard = false } = {}) {
    this.listening = false;
    cancelAnimationFrame(this.frame);
    this.stream?.getAudioTracks().forEach(track => { track.enabled = false; });
    if (discard) {
      clearTimeout(this.finalTimer);
      this.turn.clear();
      this.send({ type: 'input_audio_buffer.clear' });
      this.onPreview('');
    }
  }
  resume() {
    if (this.closed || this.listening || !this.analyser || this.channel.readyState !== 'open') return;
    this.turn.clear();
    this.detector.reset();
    this.send({ type: 'input_audio_buffer.clear' });
    this.stream.getAudioTracks().forEach(track => { track.enabled = true; });
    this.listening = true;
    this.onListening();
    this.monitor();
  }
  fail(message) {
    if (this.closed) return;
    this.close();
    this.onError(message);
  }
  close() {
    this.closed = true;
    this.pause();
    clearTimeout(this.finalTimer);
    this.controller.abort();
    this.channel?.close();
    this.pc?.close();
    this.source?.disconnect();
    this.context?.close().catch(() => {});
  }
}
