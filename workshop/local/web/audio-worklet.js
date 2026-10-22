import {PCMFramer} from './audio-utils.mjs';
class MicrophonePCM extends AudioWorkletProcessor {
  constructor() {
    super();
    this.framer = new PCMFramer(sampleRate, buffer => {
      this.port.postMessage(buffer, [buffer]);
    });
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) this.framer.push(channel);
    return true;
  }
}
registerProcessor('microphone-pcm', MicrophonePCM);
