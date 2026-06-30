r"""
Smoke-test Qwen3.5-Omni-Plus-Realtime for VerbalVis.

Checks:
1. WebSocket can connect and receives session.created.
2. A minimal session.update is accepted.
3. response.create produces a real model response.
4. The full VerbalVis Qwen session config is accepted by DashScope.

Run:
    C:\Users\admin\miniconda3\envs\VerbalVis\python.exe F:\VerbalVis2\backend\test_qwen_api.py

    C:\Users\admin\miniconda3\envs\VerbalVis\python.exe .\backend\test_qwen_api.py --region beijing --wav F:\VerbalVis2\backend\qwen_olist_test.wav --audio-mode simple --minimal-only --play --reply-wav F:\VerbalVis2\backend\qwen_olist_reply_live.wav

    cd F:\VerbalVis2
    C:\Users\admin\miniconda3\envs\VerbalVis\python.exe .\backend\test_qwen_api.py --region beijing --wav F:\VerbalVis2\backend\FD-02.wav --audio-mode simple --minimal-only --play --reply-wav F:\VerbalVis2\backend\qwen_reply.wav

    (verbalvis) PS F:\VerbalVis2> C:\Users\admin\miniconda3\envs\VerbalVis\python.exe .\backend\test_qwen_api.py --region beijing --wav F:\VerbalVis2\backend\FD-02.wav --audio-mode simple --minimal-only --play --reply-wav F:\VerbalVis2\backend\qwen_reply.wav
Using env file: F:\VerbalVis2\backend\.env
API key loaded: yes, length=116

=== WAV audio input realtime reply test (simple) ===
  wav=F:\VerbalVis2\backend\FD-02.wav converted=pcm16/mono/16000Hz duration=3.59s bytes=114816
  playback: Windows realtime output enabled
Connecting: region=beijing model=qwen3.5-omni-plus-realtime
  <- session.created
  -> session.update
  <- session.updated
  -> input_audio_buffer.append chunks=36
  -> input_audio_buffer.commit
  -> response.create
  <- input_audio_buffer.committed
  <- response.created
  <- response.output_item.added
  <- conversation.item.created
  <- response.content_part.added
  <- response.audio_transcript.delta: '没问题'
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.created
  <- conversation.item.input_audio_transcription.completed: '试图四筛选出评分低于三分的订单。'
  <- response.audio_transcript.delta: '，视图'
  <- response.audio_transcript.delta: '四已经'
  <- response.audio_transcript.delta: '筛选出所有'
  <- response.audio_transcript.delta: '评分低于三分的订单'
  <- response.audio_transcript.delta: '。'
  <- response.audio_transcript.delta: '顺便'
  <- response.audio_transcript.delta: '提一下，Olist'
  <- response.audio_transcript.delta: ' 是一个巴西电商订单'
  <- response.audio_transcript.delta: '数据集，我们可以'
  <- response.audio_transcript.delta: '用它来分析订单趋势、'
  <- response.audio_transcript.delta: '评分分布'
  <- response.audio_transcript.delta: '、地区差异'
  <- response.audio_transcript.delta: '、品类收入'
  <- response.audio_transcript.delta: '以及配送表现。'
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 15360 base64 chars
  <- response.audio_transcript.done: '没问题，视图四已经筛选出所有评分低于三分的订单。顺便提一下，Olist 是一个巴西电商订单数据集，我们可以用它来分析订单趋势、评分分布、地区差异、品类收入以及配送表现。'
  <- response.audio.done
  <- response.content_part.done
  <- response.output_item.done
  <- response.done
  reply_wav: F:\VerbalVis2\backend\qwen_reply.wav bytes=733484
  response.done=True events=85
  user_transcript: 试图四筛选出评分低于三分的订单。
  assistant_transcript: 没问题，视图四已经筛选出所有评分低于三分的订单。顺便提一下，Olist 是一个巴西电商订单数据集，我们可以用它来分析订单趋势、评分分布、地区差异、品类收入以及配送表现。
  playback: waiting for queued audio to finish

============================================================
Summary
============================================================
minimal_reply: PASS
audio_wav_reply: PASS
verbalvis_session_update: PASS
(verbalvis) PS F:\VerbalVis2> C:\Users\admin\miniconda3\envs\VerbalVis\python.exe .\backend\test_qwen_api.py --region beijing --wav F:\VerbalVis2\backend\FD-02.wav --audio-mode simple --minimal-only --play --reply-wav F:\VerbalVis2\backend\qwen_reply.wav
Using env file: F:\VerbalVis2\backend\.env
API key loaded: yes, length=116

=== WAV audio input realtime reply test (simple) ===
  wav=F:\VerbalVis2\backend\FD-02.wav converted=pcm16/mono/16000Hz duration=3.59s bytes=114816
  playback: Windows realtime output enabled
Connecting: region=beijing model=qwen3.5-omni-plus-realtime
  <- session.created
  -> session.update
  <- session.updated
  -> input_audio_buffer.append chunks=36
  -> input_audio_buffer.commit
  -> response.create
  <- input_audio_buffer.committed
  <- response.created
  <- response.output_item.added
  <- conversation.item.created
  <- response.content_part.added
  <- response.audio_transcript.delta: '没问题'
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.created
  <- conversation.item.input_audio_transcription.completed: '试图四筛选出评分低于三分的订单。'
  <- response.audio_transcript.delta: '，这就'
  <- response.audio_transcript.delta: '帮你'
  <- response.audio_transcript.delta: '把'
  <- response.audio_transcript.delta: '评分低于三分'
  <- response.audio_transcript.delta: '的订单都'
  <- response.audio_transcript.delta: '筛选出来。顺便'
  <- response.audio_transcript.delta: '提一下，我们'
  <- response.audio_transcript.delta: '用的 Olist 是一个'
  <- response.audio_transcript.delta: '巴西电商订单数据集，'
  <- response.audio_transcript.delta: '除了看评分'
  <- response.audio_transcript.delta: '，还能分析订单趋势'
  <- response.audio_transcript.delta: '、地区'
  <- response.audio_transcript.delta: '分布、品类收入和'
  <- response.audio_transcript.delta: '配送表现呢'
  <- response.audio_transcript.delta: '。'
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 15360 base64 chars
  <- response.audio_transcript.done: '没问题，这就帮你把评分低于三分的订单都筛选出来。顺便提一下，我们用的 Olist 是一个巴西电商订单数据集，除了看评分，还能分析订单趋势、地区分布、品类收入和配送表现呢。'
  <- response.audio.done
  <- response.content_part.done
  <- response.output_item.done
  <- response.done
  reply_wav: F:\VerbalVis2\backend\qwen_reply.wav bytes=779564
  response.done=True events=89
  user_transcript: 试图四筛选出评分低于三分的订单。
  assistant_transcript: 没问题，这就帮你把评分低于三分的订单都筛选出来。顺便提一下，我们用的 Olist 是一个巴西电商订单数据集，除了看评分，还能分析订单趋势、地区分布、品类收入和配送表现呢。
  playback: waiting for queued audio to finish

============================================================
Summary
============================================================
minimal_reply: PASS
audio_wav_reply: PASS
verbalvis_session_update: PASS
(verbalvis) PS F:\VerbalVis2> ^C
(verbalvis) PS F:\VerbalVis2>     C:\Users\admin\miniconda3\envs\VerbalVis\python.exe .\backend\test_qwen_api.py --region beijing --wav F:\VerbalVis2\backend\qwen_olist_test.wav --audio-mode simple --minimal-only
--play --reply-wav F:\VerbalVis2\backend\qwen_olist_reply_live.wav
Using env file: F:\VerbalVis2\backend\.env
API key loaded: yes, length=116

=== WAV audio input realtime reply test (simple) ===
  wav=F:\VerbalVis2\backend\qwen_olist_test.wav converted=pcm16/mono/16000Hz duration=3.33s bytes=106674
  playback: Windows realtime output enabled
Connecting: region=beijing model=qwen3.5-omni-plus-realtime
  <- session.created
  -> session.update
  <- session.updated
  -> input_audio_buffer.append chunks=34
  -> input_audio_buffer.commit
  -> response.create
  <- input_audio_buffer.committed
  <- response.created
  <- response.output_item.added
  <- conversation.item.created
  <- response.content_part.added
  <- response.audio_transcript.delta: '你好'
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.input_audio_transcription.delta
  <- conversation.item.created
  <- conversation.item.input_audio_transcription.completed: '你好，请介绍一下Olist。'
  <- response.audio_transcript.delta: '，Olist 是一个'
  <- response.audio_transcript.delta: '巴西电商订单数据集，'
  <- response.audio_transcript.delta: '你可以用它来分析订单趋势'
  <- response.audio_transcript.delta: '、用户'
  <- response.audio_transcript.delta: '评分、地区分布、'
  <- response.audio_transcript.delta: '品类收入以及配送'
  <- response.audio_transcript.delta: '表现。'
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio.delta: 20480 base64 chars
  <- response.audio_transcript.done: '你好，Olist 是一个巴西电商订单数据集，你可以用它来分析订单趋势、用户评分、地区分布、品类收入以及配送表现。'
  <- response.audio.done
  <- response.content_part.done
  <- response.output_item.done
  <- response.done
  reply_wav: F:\VerbalVis2\backend\qwen_olist_reply_live.wav bytes=476204
  response.done=True events=57
  user_transcript: 你好，请介绍一下Olist。
  assistant_transcript: 你好，Olist 是一个巴西电商订单数据集，你可以用它来分析订单趋势、用户评分、地区分布、品类收入以及配送表现。
  playback: waiting for queued audio to finish

============================================================
Summary
============================================================
minimal_reply: PASS
audio_wav_reply: PASS
verbalvis_session_update: PASS
(verbalvis) PS F:\VerbalVis2>


"""

from __future__ import annotations

import argparse
import base64
import ctypes
import json
import os
import queue
import ssl
import sys
import threading
import time
import uuid
import warnings
import wave
from pathlib import Path
from typing import Any

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="'audioop' is deprecated.*",
)
import audioop

from dotenv import load_dotenv

try:
    import websocket  # websocket-client
except ImportError:
    print("[FATAL] Missing dependency: pip install websocket-client python-dotenv")
    sys.exit(1)


BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
ENV_PATH = BACKEND_DIR / ".env"
MODEL = "qwen3.5-omni-plus-realtime"
DEFAULT_VOICE = "Tina"
CONNECT_TIMEOUT = 15
RECV_TIMEOUT = 25

load_dotenv(ENV_PATH)

API_KEY = (os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or "").strip()
if not API_KEY:
    print(f"[FATAL] Missing QWEN_API_KEY or DASHSCOPE_API_KEY in {ENV_PATH}")
    sys.exit(1)

WORKSPACE_ID = os.getenv("QWEN_WORKSPACE_ID", "").strip()

REGION_ENDPOINTS = {
    "beijing": "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
    "singapore": (
        f"wss://{WORKSPACE_ID}.ap-southeast-1.maas.aliyuncs.com/api-ws/v1/realtime"
        if WORKSPACE_ID
        else "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
    ),
}


def qwen_url(region: str) -> str:
    return f"{REGION_ENDPOINTS[region]}?model={MODEL}"


def connect(region: str) -> websocket.WebSocket:
    print(f"Connecting: region={region} model={MODEL}")
    ws = websocket.create_connection(
        qwen_url(region),
        header=[
            f"Authorization: Bearer {API_KEY}",
            "X-DashScope-DataInspection: enable",
        ],
        timeout=CONNECT_TIMEOUT,
        sslopt={"cert_reqs": ssl.CERT_NONE},
    )
    ws.settimeout(RECV_TIMEOUT)
    return ws


def recv_event(ws: websocket.WebSocket) -> dict[str, Any]:
    raw = ws.recv()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return json.loads(raw)


def wait_for(
    ws: websocket.WebSocket,
    wanted: set[str],
    *,
    timeout: int = RECV_TIMEOUT,
    collect_transcript: bool = False,
) -> tuple[dict[str, Any] | None, list[str], str]:
    deadline = time.time() + timeout
    seen: list[str] = []
    transcript_parts: list[str] = []
    last_event: dict[str, Any] | None = None

    while time.time() < deadline:
        event = recv_event(ws)
        last_event = event
        event_type = event.get("type", "")
        seen.append(event_type)

        if event_type in {
            "response.audio_transcript.delta",
            "response.output_audio_transcript.delta",
            "response.text.delta",
        }:
            delta = event.get("delta", "")
            transcript_parts.append(delta)
            print(f"  <- {event_type}: {delta[:80]!r}")
        elif event_type in {
            "response.audio_transcript.done",
            "response.output_audio_transcript.done",
        }:
            transcript = event.get("transcript", "")
            if transcript and not transcript_parts:
                transcript_parts.append(transcript)
            print(f"  <- {event_type}: {transcript[:120]!r}")
        elif event_type == "conversation.item.input_audio_transcription.completed":
            print(f"  <- {event_type}: {event.get('transcript', '')[:160]!r}")
        else:
            print(f"  <- {event_type}")

        if event_type == "error":
            print("  [ERR]", json.dumps(event, ensure_ascii=False)[:1200])
            return event, seen, "".join(transcript_parts)

        if event_type in wanted:
            return event, seen, "".join(transcript_parts) if collect_transcript else ""

    print(f"  [TIMEOUT] Waiting for one of: {sorted(wanted)}")
    return last_event, seen, "".join(transcript_parts)


def send_session_update(ws: websocket.WebSocket, session: dict[str, Any]) -> bool:
    ws.send(json.dumps({
        "event_id": "evt_" + uuid.uuid4().hex,
        "type": "session.update",
        "session": session,
    }, ensure_ascii=False))
    print("  -> session.update")
    event, _, _ = wait_for(ws, {"session.updated"})
    return bool(event and event.get("type") == "session.updated")


def minimal_session_config() -> dict[str, Any]:
    return {
        "modalities": ["text", "audio"],
        "instructions": (
            "You are a short smoke-test assistant. Reply in one brief sentence."
        ),
        "voice": DEFAULT_VOICE,
        "input_audio_format": "pcm",
        "output_audio_format": "pcm",
        "turn_detection": None,
    }


def load_wav_as_qwen_pcm(wav_path: Path) -> tuple[bytes, float]:
    """Return 16 kHz, mono, signed 16-bit PCM bytes for Qwen Realtime."""
    if not wav_path.exists():
        raise FileNotFoundError(f"WAV file not found: {wav_path}")

    with wave.open(str(wav_path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frame_count = wav.getnframes()
        audio = wav.readframes(frame_count)

    if channels not in {1, 2}:
        raise ValueError(f"Only mono/stereo WAV is supported, got {channels} channels")
    if sample_width not in {1, 2, 3, 4}:
        raise ValueError(f"Unsupported WAV sample width: {sample_width} bytes")

    if sample_width == 1:
        # 8-bit PCM WAV is unsigned; audioop expects signed samples.
        audio = audioop.bias(audio, 1, -128)

    if sample_width != 2:
        audio = audioop.lin2lin(audio, sample_width, 2)

    if channels == 2:
        audio = audioop.tomono(audio, 2, 0.5, 0.5)

    if sample_rate != 16000:
        audio, _ = audioop.ratecv(audio, 2, 1, sample_rate, 16000, None)

    duration_seconds = len(audio) / (16000 * 2)
    if duration_seconds <= 0:
        raise ValueError("WAV has no audio data")

    return audio, duration_seconds


def append_pcm_audio(ws: websocket.WebSocket, pcm: bytes, *, chunk_ms: int = 100) -> int:
    chunk_bytes = max(320, int(16000 * 2 * chunk_ms / 1000))
    chunk_count = 0
    for offset in range(0, len(pcm), chunk_bytes):
        chunk = pcm[offset:offset + chunk_bytes]
        ws.send(json.dumps({
            "event_id": "evt_" + uuid.uuid4().hex,
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(chunk).decode("ascii"),
        }, ensure_ascii=False))
        chunk_count += 1
    return chunk_count


def write_pcm_wav(path: Path, pcm: bytes, *, sample_rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)


class RealtimePCMPlayer:
    """Play 16-bit mono PCM chunks through Windows waveOut while streaming."""

    def __init__(self, *, sample_rate: int = 24000) -> None:
        if not sys.platform.startswith("win"):
            raise RuntimeError("--play currently supports Windows only")
        self.sample_rate = sample_rate
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, name="qwen-audio-player", daemon=True)
        self._thread.start()

    def write(self, pcm: bytes) -> None:
        if pcm:
            self._queue.put(bytes(pcm))

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join()
        if self._error:
            raise self._error

    def _run(self) -> None:
        handle = ctypes.c_void_p()
        try:
            self._open(handle)
            while True:
                chunk = self._queue.get()
                if chunk is None:
                    break
                self._play_chunk(handle, chunk)
        except Exception as exc:
            self._error = exc
        finally:
            if handle.value:
                ctypes.windll.winmm.waveOutClose(handle)

    def _open(self, handle: ctypes.c_void_p) -> None:
        class WAVEFORMATEX(ctypes.Structure):
            _fields_ = [
                ("wFormatTag", ctypes.c_ushort),
                ("nChannels", ctypes.c_ushort),
                ("nSamplesPerSec", ctypes.c_uint32),
                ("nAvgBytesPerSec", ctypes.c_uint32),
                ("nBlockAlign", ctypes.c_ushort),
                ("wBitsPerSample", ctypes.c_ushort),
                ("cbSize", ctypes.c_ushort),
            ]

        block_align = 2
        fmt = WAVEFORMATEX(
            1,                 # WAVE_FORMAT_PCM
            1,                 # mono
            self.sample_rate,
            self.sample_rate * block_align,
            block_align,
            16,
            0,
        )
        result = ctypes.windll.winmm.waveOutOpen(
            ctypes.byref(handle),
            0xFFFFFFFF,        # WAVE_MAPPER
            ctypes.byref(fmt),
            0,
            0,
            0,
        )
        self._check(result, "waveOutOpen")

    def _play_chunk(self, handle: ctypes.c_void_p, chunk: bytes) -> None:
        ptr_type = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32

        class WAVEHDR(ctypes.Structure):
            _fields_ = [
                ("lpData", ctypes.c_void_p),
                ("dwBufferLength", ctypes.c_uint32),
                ("dwBytesRecorded", ctypes.c_uint32),
                ("dwUser", ptr_type),
                ("dwFlags", ctypes.c_uint32),
                ("dwLoops", ctypes.c_uint32),
                ("lpNext", ctypes.c_void_p),
                ("reserved", ptr_type),
            ]

        buffer = ctypes.create_string_buffer(chunk)
        header = WAVEHDR(
            ctypes.cast(buffer, ctypes.c_void_p),
            len(chunk),
            0,
            0,
            0,
            0,
            None,
            0,
        )
        header_size = ctypes.sizeof(WAVEHDR)
        self._check(
            ctypes.windll.winmm.waveOutPrepareHeader(handle, ctypes.byref(header), header_size),
            "waveOutPrepareHeader",
        )
        try:
            self._check(
                ctypes.windll.winmm.waveOutWrite(handle, ctypes.byref(header), header_size),
                "waveOutWrite",
            )
            while not (header.dwFlags & 0x00000001):  # WHDR_DONE
                time.sleep(0.005)
        finally:
            ctypes.windll.winmm.waveOutUnprepareHeader(handle, ctypes.byref(header), header_size)

    @staticmethod
    def _check(result: int, action: str) -> None:
        if result:
            raise RuntimeError(f"{action} failed with WinMM error code {result}")


def simple_audio_session_config() -> dict[str, Any]:
    session = minimal_session_config()
    session["instructions"] = (
        "你是 VerbalVis 的音频链路测试助手。用户会用中文语音问你问题。"
        "请用中文简短回答，并介绍 Olist 是一个巴西电商订单数据集，"
        "可以分析订单趋势、评分、地区、品类收入和配送表现。"
    )
    return session


def tool_result_text(result: dict[str, Any]) -> str:
    return json.dumps({
        "success": result.get("success", False),
        "payload": result.get("payload"),
        "error": result.get("error"),
        "warning": result.get("warning"),
    }, ensure_ascii=False, default=str)


def handle_verbalvis_tool_call(event: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, str(BACKEND_DIR))
    from tools import context_text, execute_tool, get_views_for_frontend

    name = event.get("name", "")
    call_id = event.get("call_id", "")
    args_text = event.get("arguments") or "{}"
    try:
        arguments = json.loads(args_text)
    except json.JSONDecodeError:
        arguments = {}

    print(f"  [TOOL] call name={name} call_id={call_id} args={arguments}")
    result = execute_tool(name, arguments)
    print(
        "  [TOOL] result "
        f"success={result.get('success')} error={result.get('error')} "
        f"payload={json.dumps(result.get('payload'), ensure_ascii=False, default=str)[:500]}"
    )
    return {
        "name": name,
        "call_id": call_id,
        "arguments": arguments,
        "result": result,
        "views": get_views_for_frontend(),
        "context": context_text(),
    }


def wait_for_audio_response(
    ws: websocket.WebSocket,
    *,
    timeout: int,
    handle_tools: bool,
    reply_wav: Path | None = None,
    player: RealtimePCMPlayer | None = None,
) -> tuple[bool, str, str, list[dict[str, Any]]]:
    deadline = time.time() + timeout
    seen: list[str] = []
    assistant_parts: list[str] = []
    user_transcript = ""
    tool_calls: list[dict[str, Any]] = []
    reply_audio = bytearray()
    sent_tool_response = False
    assistant_transcript_done = False

    while time.time() < deadline:
        event = recv_event(ws)
        event_type = event.get("type", "")
        seen.append(event_type)

        if event_type in {
            "response.audio_transcript.delta",
            "response.output_audio_transcript.delta",
            "response.text.delta",
        }:
            delta = event.get("delta", "")
            assistant_parts.append(delta)
            print(f"  <- {event_type}: {delta[:80]!r}")
        elif event_type in {
            "response.audio_transcript.done",
            "response.output_audio_transcript.done",
        }:
            assistant_transcript_done = True
            transcript = event.get("transcript", "")
            if transcript and not assistant_parts:
                assistant_parts.append(transcript)
            print(f"  <- {event_type}: {transcript[:160]!r}")
        elif event_type == "conversation.item.input_audio_transcription.completed":
            user_transcript = event.get("transcript", "")
            print(f"  <- {event_type}: {user_transcript[:200]!r}")
        elif event_type in {"response.audio.delta", "response.output_audio.delta"}:
            delta = event.get("delta", "")
            if delta:
                pcm_chunk = base64.b64decode(delta)
                reply_audio.extend(pcm_chunk)
                if player:
                    player.write(pcm_chunk)
            print(f"  <- {event_type}: {len(delta)} base64 chars")
        elif event_type == "response.function_call_arguments.done":
            print("  <- response.function_call_arguments.done")
            if not handle_tools:
                print("  [WARN] Tool call received but tool handling is disabled")
                continue
            tool_call = handle_verbalvis_tool_call(event)
            tool_calls.append(tool_call)
            ws.send(json.dumps({
                "event_id": "evt_" + uuid.uuid4().hex,
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": tool_call["call_id"],
                    "output": tool_result_text(tool_call["result"]),
                },
            }, ensure_ascii=False))
            print("  -> conversation.item.create function_call_output")
            ws.send(json.dumps({
                "event_id": "evt_" + uuid.uuid4().hex,
                "type": "response.create",
            }, ensure_ascii=False))
            print("  -> response.create after tool")
            sent_tool_response = True
        elif event_type == "error":
            print("  [ERR]", json.dumps(event, ensure_ascii=False)[:1200])
            return False, user_transcript, "".join(assistant_parts), tool_calls
        else:
            print(f"  <- {event_type}")

        if event_type == "response.done":
            if not sent_tool_response or assistant_transcript_done or assistant_parts:
                if reply_wav and reply_audio:
                    write_pcm_wav(reply_wav, bytes(reply_audio), sample_rate=24000)
                    print(f"  reply_wav: {reply_wav} bytes={reply_wav.stat().st_size}")
                print(f"  response.done=True events={len(seen)}")
                return True, user_transcript, "".join(assistant_parts), tool_calls

    print(f"  [TIMEOUT] events={len(seen)}")
    return False, user_transcript, "".join(assistant_parts), tool_calls


def test_wav_audio_reply(
    region: str,
    wav_path: Path,
    *,
    audio_mode: str,
    reply_wav: Path | None,
    play_audio: bool,
) -> bool:
    print(f"\n=== WAV audio input realtime reply test ({audio_mode}) ===")
    pcm, duration_seconds = load_wav_as_qwen_pcm(wav_path)
    print(
        f"  wav={wav_path} converted=pcm16/mono/16000Hz "
        f"duration={duration_seconds:.2f}s bytes={len(pcm)}"
    )

    if audio_mode == "verbalvis":
        session_config = build_verbalvis_session_config()
        handle_tools = True
    else:
        session_config = simple_audio_session_config()
        handle_tools = False

    player: RealtimePCMPlayer | None = None
    if play_audio:
        print("  playback: Windows realtime output enabled")
        player = RealtimePCMPlayer(sample_rate=24000)

    ws = connect(region)
    try:
        event, _, _ = wait_for(ws, {"session.created"})
        if not event or event.get("type") != "session.created":
            return False

        if not send_session_update(ws, session_config):
            return False

        chunk_count = append_pcm_audio(ws, pcm)
        print(f"  -> input_audio_buffer.append chunks={chunk_count}")

        ws.send(json.dumps({
            "event_id": "evt_" + uuid.uuid4().hex,
            "type": "input_audio_buffer.commit",
        }, ensure_ascii=False))
        print("  -> input_audio_buffer.commit")

        ws.send(json.dumps({
            "event_id": "evt_" + uuid.uuid4().hex,
            "type": "response.create",
        }, ensure_ascii=False))
        print("  -> response.create")

        ok, user_transcript, assistant_transcript, tool_calls = wait_for_audio_response(
            ws,
            timeout=60,
            handle_tools=handle_tools,
            reply_wav=reply_wav,
            player=player,
        )
        print(f"  user_transcript: {user_transcript or '(no user transcript captured)'}")
        print(f"  assistant_transcript: {assistant_transcript[:500] or '(no assistant transcript captured)'}")
        if handle_tools:
            print(f"  tool_calls={len(tool_calls)}")
            for tool_call in tool_calls:
                print(
                    "    - "
                    f"{tool_call['name']} args={tool_call['arguments']} "
                    f"success={tool_call['result'].get('success')}"
                )
        return ok
    finally:
        try:
            ws.close()
        finally:
            if player:
                print("  playback: waiting for queued audio to finish")
                player.close()


def test_minimal_reply(region: str) -> bool:
    print("\n=== Minimal realtime reply test ===")
    ws = connect(region)
    try:
        event, _, _ = wait_for(ws, {"session.created"})
        if not event or event.get("type") != "session.created":
            return False

        if not send_session_update(ws, minimal_session_config()):
            return False

        ws.send(json.dumps({
            "event_id": "evt_" + uuid.uuid4().hex,
            "type": "response.create",
        }, ensure_ascii=False))
        print("  -> response.create")
        event, seen, transcript = wait_for(
            ws,
            {"response.done"},
            timeout=40,
            collect_transcript=True,
        )
        ok = bool(event and event.get("type") == "response.done")
        print(f"  transcript: {transcript[:300] or '(no transcript captured)'}")
        print(f"  response.done={ok} events={len(seen)}")
        return ok
    finally:
        ws.close()


def build_verbalvis_session_config() -> dict[str, Any]:
    sys.path.insert(0, str(BACKEND_DIR))
    from db import initialize_db
    from tools import context_text, init_views
    from realtime_qwen import QwenRealtimeSession

    initialize_db()
    init_views()
    session = QwenRealtimeSession(client_ws=None, session_id="smoke-test")
    session._dashboard_context = context_text()
    return session._build_session_config()


def test_verbalvis_session_update(region: str) -> bool:
    print("\n=== VerbalVis full session.update test ===")
    config = build_verbalvis_session_config()
    encoded = json.dumps(config, ensure_ascii=False)
    has_type_list = '"type": [' in encoded
    print(
        f"  voice={config.get('voice')} tools={len(config.get('tools', []))} "
        f"type_list={has_type_list}"
    )

    ws = connect(region)
    try:
        event, _, _ = wait_for(ws, {"session.created"})
        if not event or event.get("type") != "session.created":
            return False
        return send_session_update(ws, config)
    finally:
        ws.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--region",
        choices=sorted(REGION_ENDPOINTS),
        default=os.getenv("QWEN_REGION", "beijing").strip().lower() or "beijing",
    )
    parser.add_argument(
        "--minimal-only",
        action="store_true",
        help="Skip the full VerbalVis session.update schema test.",
    )
    parser.add_argument(
        "--wav",
        type=Path,
        help=(
            "Send a local WAV file as user audio. The script converts it to "
            "16 kHz mono PCM and checks that Qwen Realtime replies."
        ),
    )
    parser.add_argument(
        "--audio-mode",
        choices=["verbalvis", "simple"],
        default="verbalvis",
        help=(
            "For --wav: use full VerbalVis instructions/tools, or a simple "
            "audio smoke-test prompt."
        ),
    )
    parser.add_argument(
        "--reply-wav",
        type=Path,
        help="Save Qwen's output audio deltas as a 24 kHz mono PCM WAV file.",
    )
    parser.add_argument(
        "--play",
        action="store_true",
        help="Play Qwen's output audio in real time while response.audio.delta streams in.",
    )
    args = parser.parse_args()

    if args.region not in REGION_ENDPOINTS:
        print(f"[FATAL] Unsupported region: {args.region}")
        return 2

    print(f"Using env file: {ENV_PATH}")
    print(f"API key loaded: yes, length={len(API_KEY)}")

    audio_ok = True
    if args.wav:
        minimal_ok = True
        audio_ok = test_wav_audio_reply(
            args.region,
            args.wav,
            audio_mode=args.audio_mode,
            reply_wav=args.reply_wav,
            play_audio=args.play,
        )
    else:
        minimal_ok = test_minimal_reply(args.region)
    verbalvis_ok = True if args.minimal_only else test_verbalvis_session_update(args.region)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"minimal_reply: {'PASS' if minimal_ok else 'FAIL'}")
    if args.wav:
        print(f"audio_wav_reply: {'PASS' if audio_ok else 'FAIL'}")
    print(f"verbalvis_session_update: {'PASS' if verbalvis_ok else 'FAIL'}")
    return 0 if minimal_ok and audio_ok and verbalvis_ok else 1


if __name__ == "__main__":
    sys.exit(main())
