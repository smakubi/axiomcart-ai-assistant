// Stateful box-filter resampling for the teaching WebSocket microphone.
export class PCMFramer {
  constructor(rate, emit) {
    this.ratio = rate / 24000;
    this.emit = emit;
    this.phase = this.sum = this.index = 0;
    this.buffer = new ArrayBuffer(960);
    this.view = new DataView(this.buffer);
  }
  push(samples) {
    for (const sample of samples) {
      let left = 1;
      while (left > 1e-8) {
        const take = Math.min(left, this.ratio - this.phase);
        this.sum += sample * take;
        this.phase += take;
        left -= take;
        if (this.phase >= this.ratio - 1e-8) {
          const value = Math.max(-1, Math.min(1, this.sum / this.ratio));
          this.view.setInt16(this.index * 2, Math.round(value * 32767), true);
          this.index++;
          this.phase = this.sum = 0;
          if (this.index === 480) {
            this.emit(this.buffer);
            this.buffer = new ArrayBuffer(960);
            this.view = new DataView(this.buffer);
            this.index = 0;
          }
        }
      }
    }
  }
}

export class EpochPlayer {
  constructor(context, ack) {
    this.context = context;
    this.ack = ack;
    this.epoch = 0;
    this.sources = new Set();
    this.next = 0;
  }
  reset(epoch) {
    this.epoch = epoch;
    for (const source of this.sources) {
      source.onended = null;
      source.stop();
      source.disconnect();
    }
    this.sources.clear();
    this.next = 0;
  }
  play(event) {
    if (event.epoch !== this.epoch) return;
    if (this.sources.size >= 8) throw new Error('Playback queue full; reconnect.');
    const bytes = Uint8Array.from(atob(event.pcm), c => c.charCodeAt(0));
    if (bytes.length !== 960) throw new Error('Invalid PCM output frame.');
    const view = new DataView(bytes.buffer);
    const buffer = this.context.createBuffer(1, 480, 24000);
    const audio = buffer.getChannelData(0);
    for (let i = 0; i < 480; i++) audio[i] = view.getInt16(i * 2, true) / 32768;
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    this.sources.add(source);
    source.onended = () => {
      this.sources.delete(source);
      source.disconnect();
      if (event.epoch === this.epoch) this.ack(event.seq);
    };
    if (this.sources.size === 1) this.next = Math.max(this.next, this.context.currentTime + 0.12);
    const at = Math.max(this.context.currentTime, this.next);
    this.next = at + 0.02;
    source.start(at);
  }
}
