import {EpochPlayer} from './audio-utils.mjs';
const $ = id => document.getElementById(id);
let active = null;
let generation = 0;
const lines = [];
function log(text) {
  lines.push(text);
  if (lines.length > 60) lines.shift();
  $('log').textContent = lines.join('\n');
}
function controls(busy) {
  $('start').disabled = busy;
  $('stop').disabled = !busy;
  $('transport').disabled = busy;
  $('barge').disabled = busy;
  $('cancel').disabled = !busy;
}
async function release(state) {
  if (!state || state.closed) return;
  state.closed = true;
  state.player?.reset(-1);
  state.socket?.close();
  state.channel?.close();
  state.pc?.close();
  state.node?.disconnect();
  state.source?.disconnect();
  state.stream?.getTracks().forEach(track => track.stop());
  if (state.context) await state.context.close();
  if (state.id) {
    await fetch(`/session/${state.id}`, {method: 'DELETE', keepalive: true}).catch(() => {});
  }
}
async function stop() {
  generation++;
  const old = active;
  active = null;
  $('remote').srcObject = null;
  controls(false);
  $('status').textContent = 'Disconnected';
  await release(old);
}
function event(state, message) {
  if (state !== active || state.closed) return;
  if (message.type === 'audio') {
    state.player.play(message);
  } else if (message.type === 'reset') {
    state.player?.reset(message.epoch);
  } else if (message.type === 'speech_start') {
    log(message.interrupted ? 'Barge-in: old reply cancelled.' : 'User speech detected.');
  } else if (message.type === 'first_audio') {
    log(`First output queued after turn end: ${message.ms} ms (not acoustic onset).`);
  } else {
    log(`${message.type}: ${message.text ?? (message.offline ? 'offline tone mode' : '')}`);
  }
}
async function iceComplete(pc) {
  if (pc.iceGatheringState === 'complete') return;
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {cleanup(); reject(new Error('ICE gathering timed out'));}, 10000);
    const check = () => {if (pc.iceGatheringState === 'complete') {cleanup(); resolve();}};
    const cleanup = () => {clearTimeout(timer); pc.removeEventListener('icegatheringstatechange', check);};
    pc.addEventListener('icegatheringstatechange', check);
    check();
  });
}
async function start() {
  await stop();
  const token = generation;
  const state = {closed: false};
  active = state;
  controls(true);
  $('status').textContent = 'Requesting microphone…';
  try {
    // User gesture creates/resumes the audio context before asynchronous permission work.
    state.context = new AudioContext();
    await state.context.resume();
    state.stream = await navigator.mediaDevices.getUserMedia({audio: {
      channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: false,
    }});
    if (token !== generation || state !== active) {
      state.stream.getTracks().forEach(track => track.stop());
      return;
    }
    state.stream.getTracks().forEach(track => track.addEventListener('ended', () => {
      if (state === active) void stop();
    }));
    const barge = $('barge').checked;
    if ($('transport').value === 'ws') {
      const socket = state.socket = new WebSocket(`ws://${location.host}/ws?barge_in=${barge ? 1 : 0}`);
      const send = message => {if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));};
      state.player = new EpochPlayer(state.context, seq => send({type: 'played', seq}));
      socket.onmessage = message => {
        try {event(state, JSON.parse(message.data));}
        catch (error) {log(error.message); if (state === active) void stop();}
      };
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('WebSocket setup timed out')), 10000);
        socket.onopen = () => {clearTimeout(timer); resolve();};
        socket.onerror = () => {clearTimeout(timer); reject(new Error('WebSocket connection failed'));};
        socket.onclose = () => {
          clearTimeout(timer);
          reject(new Error('WebSocket closed'));
          if (state === active) {log('Connection ended.'); void stop();}
        };
      });
      if (state !== active) return;
      await state.context.audioWorklet.addModule('/audio-worklet.js');
      if (state !== active) return;
      state.source = state.context.createMediaStreamSource(state.stream);
      state.node = new AudioWorkletNode(state.context, 'microphone-pcm');
      state.node.port.onmessage = e => {
        if (socket.readyState !== WebSocket.OPEN) return;
        if (socket.bufferedAmount > 48000) {
          log('Microphone send queue exceeded one second; reconnect.'); void stop(); return;
        }
        socket.send(e.data);
      };
      state.source.connect(state.node);
      // Worklet emits silence; connecting its output keeps capture processing active.
      state.node.connect(state.context.destination);
    } else {
      const pc = state.pc = new RTCPeerConnection({iceServers: []});
      state.channel = pc.createDataChannel('events');
      state.channel.onmessage = e => {try {event(state, JSON.parse(e.data));} catch (error) {log(error.message);}};
      pc.ontrack = e => {
        if (state !== active) return;
        $('remote').srcObject = new MediaStream([e.track]);
        $('remote').play().catch(() => {log('Playback blocked; click Start again.'); void stop();});
      };
      pc.onconnectionstatechange = () => {
        if (state === active && ['failed', 'closed', 'disconnected'].includes(pc.connectionState)) {
          log(`WebRTC ${pc.connectionState}`); void stop();
        }
      };
      state.stream.getAudioTracks().forEach(track => pc.addTrack(track, state.stream));
      await pc.setLocalDescription(await pc.createOffer());
      await iceComplete(pc);
      if (state !== active) return;
      const response = await fetch('/offer', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({sdp: pc.localDescription.sdp, type: 'offer', barge_in: barge}),
        signal: AbortSignal.timeout(20000)});
      if (!response.ok) throw new Error(`WebRTC setup failed (${response.status}); check server configuration.`);
      const answer = await response.json();
      state.id = answer.id;
      if (state !== active) {
        await fetch(`/session/${answer.id}`, {method: 'DELETE'});
        return;
      }
      await pc.setRemoteDescription({type: answer.type, sdp: answer.sdp});
    }
    if (state === active) $('status').textContent = 'Microphone active — speak, then pause.';
  } catch (error) {
    if (state === active) {log(error.message); await stop();}
    else await release(state);
  }
}
$('start').onclick = () => void start();
$('stop').onclick = () => void stop();
$('cancel').onclick = () => {
  if (active?.socket?.readyState === WebSocket.OPEN) active.socket.send(JSON.stringify({type: 'stop_reply'}));
  if (active?.channel?.readyState === 'open') active.channel.send('stop_reply');
};
window.addEventListener('pagehide', () => {void stop();});
