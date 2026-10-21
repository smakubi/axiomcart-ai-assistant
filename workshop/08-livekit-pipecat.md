# Exercise 8 — Why use LiveKit or Pipecat?

This lesson follows the runnable Python cascade in [local/README.md](local/README.md). **Run the local implementation first.** The snippets below explain framework structure; they are not stand-alone runnable applications. To run a framework, follow its official quickstart and configure its transport, model credentials, and session entrypoint.

## Start with the problem
Our local code records, transcribes, thinks, synthesizes, and plays **sequentially**. What happens if the customer interrupts during playback? The microphone isn't being monitored, so the assistant cannot hear the interruption.

Ask students to design two simultaneous tasks: one continuously monitoring user input, the other streaming output. How do they share cancellation state? What happens to old TTS chunks after interruption?

## Pipecat — processors and frames
Pipecat expresses a voice pipeline as a sequence of processors. Each consumes and emits typed frames. A conceptual shape from the documentation:

```python
from pipecat.pipeline.pipeline import Pipeline

# Initialize transport, stt, context_aggregator, llm, tts first.
pipeline = Pipeline([
    transport.input(),
    stt,
    context_aggregator.user(),
    llm,
    tts,
    transport.output(),
    context_aggregator.assistant(),
])
```

Map it back to our code:
- `record_fixed` / `record_until_silence` → input transport + turn processing
- `transcribe` → STT processor
- `think` → LLM processor
- `speak` / `play_wav` → TTS processor + output transport
- manually maintained control flow → frame pipeline and task runner

Pipecat supports SmallWebRTC for local/self-hosted browser-to-server voice and Daily for managed real-time transport. A real implementation needs initialized processors, a pipeline task/runner, a server transport and a client.

## LiveKit Agents — session-oriented orchestration
LiveKit's `AgentSession` ties together the models and handles turn detection, interruptions, media I/O, and tools.

```python
from livekit.agents import AgentSession, Agent

session = AgentSession(
    stt="deepgram/flux-general",
    llm="openai/gpt-4.1-mini",
    tts="cartesia/sonic-3",
)
agent = Agent(instructions="You are a concise shopping assistant.")
```

This is **configuration only**, not a runnable agent. You also need a LiveKit worker/entrypoint, room connection, credentials, and supported model/voice configuration. For a runnable version, start from the official LiveKit Python voice quickstart.

Map it back to our code:
- explicit function-by-function orchestration → `AgentSession`
- custom silence detection → configured VAD / turn handling
- microphone/speaker transport → LiveKit real-time media I/O
- application prompt → `Agent(instructions=...)`

## Guided comparison
| Question | Local Python | Pipecat | LiveKit Agents |
| --- | --- | --- | --- |
| Where is the cascade? | `cascade()` | Pipeline processor sequence | `AgentSession` |
| Who owns microphone transport? | `sounddevice` | Transport plugin | Room / audio I/O |
| Who handles turn lifecycle? | Our detector and loop | Framework processors | Session runtime |
| Can user interrupt TTS? | Not in this baseline | Framework support | Framework support |
| Can we insert custom processing? | Edit our functions | Insert a processor | Plugins / hooks |

## Student experiment
1. Run `python voice.py loop` and try speaking while the assistant is talking. Observe that it doesn't hear you.
2. Sketch how to fix that with a microphone task and a playback task sharing a cancellation event.
3. Read the two framework snippets. Identify which lines replace the responsibilities you just sketched.
4. Explain the tradeoff: fewer lines of application orchestration, but more framework-specific concepts and infrastructure.

## Discussion prompts
- Does a framework eliminate STT or TTS inference? No; it coordinates them.
- Is WebRTC the same thing as STT? No; WebRTC transports media.
- Is Pipecat always faster than LiveKit? No; benchmark with the same models, transport conditions, and turn policies.
- Why might a team choose a framework? Interruptions, streaming, integrations, observability, transport, and maintenance.
- Why might a team keep a simple custom loop? Small offline/batch tasks or a teaching demo where real-time interactivity isn't needed.

## Official references
- https://docs.pipecat.ai/client/concepts/choosing-a-transport
- https://github.com/pipecat-ai/docs/blob/main/pipecat/learn/llm.mdx
- https://docs.livekit.io/agents/logic/sessions/
- https://docs.livekit.io/agents/start/voice-ai/

**Instructor note:** This is a comparison lesson. Do not claim LiveKit or Pipecat examples were locally tested; neither is wired into this repository yet.
