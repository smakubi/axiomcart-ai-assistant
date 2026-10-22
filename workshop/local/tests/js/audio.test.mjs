import test from 'node:test';
import assert from 'node:assert/strict';
import {PCMFramer, EpochPlayer} from '../../web/audio-utils.mjs';

test('microphone resampling preserves frame boundaries at 48 kHz and 44.1 kHz', () => {
  for (const rate of [48000, 44100]) {
    const frames = [];
    const framer = new PCMFramer(rate, pcm => frames.push(pcm));
    const input = new Float32Array(rate / 10).fill(.5);
    for (let i = 0; i < input.length; i += 128) framer.push(input.slice(i, i + 128));
    assert.equal(frames.length, 5);
    assert.equal(frames[0].byteLength, 960);
    assert.equal(new DataView(frames[0]).getInt16(0, true), 16384);
  }
});

test('reset stops queued sources and stale audio cannot start again', () => {
  let starts = 0, stops = 0, acknowledgments = 0;
  const sources = [];
  const context = {currentTime: 1, destination: {},
    createBuffer: () => ({getChannelData: () => new Float32Array(480)}),
    createBufferSource: () => {
      const source = {connect() {}, disconnect() {}, start() {starts++;}, stop() {stops++;}};
      sources.push(source); return source;
    }};
  const player = new EpochPlayer(context, () => acknowledgments++);
  const event = {epoch: 0, seq: 1, pcm: Buffer.alloc(960).toString('base64')};
  player.play(event);
  player.reset(1);
  player.play(event);
  assert.equal(starts, 1);
  assert.equal(stops, 1);
  assert.equal(sources[0].onended, null);
  assert.equal(acknowledgments, 0);
  player.play({...event, epoch: 1});
  sources[1].onended();
  assert.equal(acknowledgments, 1);
});
