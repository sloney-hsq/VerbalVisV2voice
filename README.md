# VerbalVis-FD-Voice

VerbalVis-FD-Voice is a full-duplex voice-only visual analytics prototype for
the Olist dashboard. It supports continuous microphone input, Qwen semantic
VAD, live user transcription, assistant speech and text output, dashboard tool
calls, user barge-in during assistant playback, and experiment logs.

Text-CVA, Voice/Text switching, text input, `/ws/text`, and `/ws/qwen` are not
part of this project.

## Runtime

- Model: `qwen3.5-omni-plus-realtime`
- Voice: `Ethan`
- Input audio: 16 kHz PCM16
- Output audio: 24 kHz PCM16
- Turn Detection: `semantic_vad`
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- WebSocket: `ws://localhost:8000/ws`

## Environment

```env
DASHSCOPE_API_KEY=你的API_KEY
QWEN_REGION=beijing
```

`QWEN_API_KEY` is also supported as a compatible fallback.

## Start

```bat
cd /d F:\VerbalVis2\backend
uvicorn main:app --reload --port 8000
```

```bat
cd /d F:\VerbalVis2\frontend
npm install
npm run dev -- --port 5173
```

Open:

```text
http://localhost:5173
```

## Interruption Boundary

Only Qwen `input_audio_buffer.speech_started` stops old assistant output.
Browser RMS detection is used only for local audio activity and does not pause
assistant audio, stop assistant audio, or send `response.cancel`.

When `speech_started` arrives while a Qwen response is still active, the backend
marks that response interrupted, asks the frontend to stop playback, clears the
streaming assistant transcript, and sends `response.cancel`. If Qwen generation
has already completed and only buffered browser audio is still playing, the
backend stops frontend playback without sending `response.cancel`.

## Non-preemptive Tool Boundary

Dashboard tool execution is intentionally non-preemptive. Once a tool batch has
started, the batch is allowed to finish normally. The project does not implement
stale-tool invalidation, rollback, transactions, epochs, or thread cancellation.

While a tool batch is running:

- the backend ignores new browser audio chunks;
- the frontend also stops sending microphone chunks;
- all calls in the current batch use the user transcript captured when the batch
  started;
- the backend emits `tool_execution_started` and `tool_execution_finished` so the
  client can track the boundary;
- after the batch finishes, microphone streaming resumes and Qwen generates the
  natural-language/audio result.

Tools are extracted only from `response.done`. Before tool execution, the
backend still discards interrupted responses, stale response completions, and
non-completed responses. A tool that has already entered `execute_tool()` is
allowed to finish and update the dashboard.

Frontend playback completion is reported with `playback_stopped`, including
`reason=natural_end` for normal playback completion. The backend uses that
receipt to clear `playback_response_id`.

## Validation Commands

```bat
cd /d F:\VerbalVis2\backend
python -m compileall .
```

```bat
cd /d F:\VerbalVis2\frontend
npm run build
```
