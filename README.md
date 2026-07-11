# VerbalVis-FD-Voice

VerbalVis-FD-Voice is a full-duplex, voice-only visual analytics prototype for
the Olist dashboard. It supports continuous microphone input, Qwen semantic VAD,
live user transcription, assistant speech and text output, dashboard tools,
barge-in during assistant playback, and experiment logs.

Text-CVA, Voice/Text switching, text input, `/ws/text`, and `/ws/qwen` are not
part of this project.

## Runtime

- Model: `qwen3.5-omni-plus-realtime`
- Voice: `Ethan`
- Input audio: 16 kHz PCM16
- Output audio: 24 kHz PCM16
- Turn detection: `semantic_vad`
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

## Interaction Boundary

Only Qwen `input_audio_buffer.speech_started` stops an old assistant response.
Browser RMS activity does not pause assistant audio, stop playback, or send
`response.cancel`.

When `speech_started` arrives while a Qwen response is active, the backend marks
that response interrupted, asks the frontend to stop playback, clears the
streaming assistant transcript, and sends `response.cancel`. If generation has
already completed and only buffered browser audio remains, the backend stops
frontend playback without sending `response.cancel`.

## Non-preemptive Tool Boundary

Dashboard tool execution is intentionally non-preemptive. Once a tool batch has
started, it is allowed to finish normally. The project does not implement:

- stale-tool invalidation;
- rollback or transactions;
- intent epochs;
- tool-thread cancellation.

While a tool batch is running:

- the backend ignores new browser audio chunks;
- the frontend also stops sending microphone chunks;
- all calls use the completed user transcript captured for that batch;
- at most four calls are accepted from one model response;
- the browser receives `tool_execution_started`, `tool_execution_finished`,
  `runtime_state`, and `dashboard_state` events;
- the microphone stream resumes after the post-tool Qwen response is requested.

A tool that has already entered `execute_tool()` is allowed to finish and update
the dashboard.

## Tool Design

The runtime keeps a small tool set with explicit contracts:

- data scope: `filter_data`, `remove_filter`;
- data definition: `set_low_score_threshold`;
- visualization: `append_visual`, `delete_visual`;
- attention: `highlight_visual`;
- evidence reading: `inspect_visual`.

`inspect_visual` is the authoritative source for chart values and statistics.
Dashboard metadata is used only to locate views and describe their configuration.
The prompt asks the model to use the smallest necessary tool chain and to avoid
repeated or speculative dashboard mutations.

## Dashboard State Feedback

The frontend includes a shared runtime panel showing:

- current phase: ready, listening, processing, speaking, reading, or updating;
- active tool names;
- global filter count;
- view count;
- current low-score definition;
- filtered row count when available;
- tool failures and the temporary microphone pause during tool execution.

This state feedback is informational. It does not add direct-manipulation controls
that would change the voice-only study condition.

## Logs

The original multi-file logs are preserved. Non-preemptive tool batches also
write `tool_execution.jsonl`, including batch duration, success/failure counts,
ignored audio chunks, and whether the post-tool response was requested.

Frontend playback completion is reported with `playback_stopped`, including
`reason=natural_end` for normal completion.

## Validation Commands

```bat
cd /d F:\VerbalVis2\backend
python -m compileall .
```

```bat
cd /d F:\VerbalVis2\frontend
npm run build
```
