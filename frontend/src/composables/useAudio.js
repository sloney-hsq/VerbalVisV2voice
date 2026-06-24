import { ref, onBeforeUnmount } from "vue";

const SAMPLE_RATE = 24000; // Realtime API PCM16 rate

/**
 * Audio composable – handles microphone capture and PCM16 playback.
 */
export function useAudio() {
  const isRecording = ref(false);

  let audioCtx = null;
  let mediaStream = null;
  let workletNode = null;
  let onAudioChunk = null; // callback: (base64pcm) => void

  // ---- Playback state ----
  let playbackCtx = null;
  const playbackQueue = [];
  let isPlaying = false;
  let nextPlayTime = 0;

  // ------------------------------------------------------------------
  // Recording (mic → PCM16 base64 chunks)
  // ------------------------------------------------------------------

  async function startRecording(chunkCallback) {
    onAudioChunk = chunkCallback;

    audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });

    // Register worklet for PCM capture
    const workletCode = `
      class PCMProcessor extends AudioWorkletProcessor {
        process(inputs) {
          const input = inputs[0];
          if (input && input[0]) {
            const float32 = input[0];
            const int16 = new Int16Array(float32.length);
            for (let i = 0; i < float32.length; i++) {
              const s = Math.max(-1, Math.min(1, float32[i]));
              int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            this.port.postMessage(int16.buffer, [int16.buffer]);
          }
          return true;
        }
      }
      registerProcessor('pcm-processor', PCMProcessor);
    `;
    const blob = new Blob([workletCode], { type: "application/javascript" });
    const url = URL.createObjectURL(blob);
    await audioCtx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);

    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: SAMPLE_RATE, channelCount: 1, echoCancellation: true },
    });

    const source = audioCtx.createMediaStreamSource(mediaStream);
    workletNode = new AudioWorkletNode(audioCtx, "pcm-processor");

    workletNode.port.onmessage = (event) => {
      if (onAudioChunk) {
        const b64 = _arrayBufferToBase64(event.data);
        console.log("worklet chunk", b64.length);
        onAudioChunk(b64);
      }
    };

    source.connect(workletNode);
    workletNode.connect(audioCtx.destination); // needed to keep processing
    isRecording.value = true;
  }

  function stopRecording() {
    isRecording.value = false;
    if (workletNode) {
      workletNode.disconnect();
      workletNode = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
    if (audioCtx) {
      audioCtx.close();
      audioCtx = null;
    }
    onAudioChunk = null;
  }

  // ------------------------------------------------------------------
  // Playback (base64 PCM16 → speakers)
  // ------------------------------------------------------------------

  function _ensurePlaybackCtx() {
    if (!playbackCtx || playbackCtx.state === "closed") {
      playbackCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
    }
    return playbackCtx;
  }

  function enqueue(base64pcm) {
    const ctx = _ensurePlaybackCtx();
    const raw = atob(base64pcm);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 0x8000;
    }

    const buffer = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
    buffer.getChannelData(0).set(float32);

    const now = ctx.currentTime;
    if (nextPlayTime < now) nextPlayTime = now;

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start(nextPlayTime);
    nextPlayTime += buffer.duration;
  }

  function flush() {
    // No-op: audio plays to completion naturally
  }

  function stop() {
    // Hard stop: close context and reset
    if (playbackCtx && playbackCtx.state !== "closed") {
      playbackCtx.close();
    }
    playbackCtx = null;
    nextPlayTime = 0;
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  function _arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  onBeforeUnmount(() => {
    stopRecording();
    stop();
  });

  function getMicStream() {
    return mediaStream;
  }

  return {
    isRecording,
    startRecording,
    stopRecording,
    getMicStream,
    // Playback interface (passed to useWebSocket)
    enqueue,
    flush,
    stop,
  };
}
