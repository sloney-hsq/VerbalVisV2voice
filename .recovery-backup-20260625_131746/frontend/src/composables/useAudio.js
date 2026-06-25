import { ref, onBeforeUnmount } from "vue";

const SAMPLE_RATE = 24000; // Realtime API PCM16 rate
const CHUNK_MS = 100;
const CHUNK_SIZE = Math.round((SAMPLE_RATE * CHUNK_MS) / 1000);
const PREFIX_CHUNKS = 3;
const TRAILING_SILENCE_CHUNKS = 5;
const SPEECH_RMS_THRESHOLD = 0.008;
const SILENCE_RMS_THRESHOLD = 0.005;

/**
 * Audio composable – handles microphone capture and PCM16 playback.
 */
export function useAudio() {
  const isRecording = ref(false);
  const isMicReady = ref(false);

  let audioCtx = null;
  let mediaStream = null;
  let sourceNode = null;
  let workletNode = null;
  let onAudioChunk = null; // callback: (base64pcm) => void
  let onSpeechStart = null;
  let onSpeechEnd = null;
  let shouldStartSpeech = null;
  let gateSilence = true;
  let setupPromise = null;
  let recordingRequestId = 0;
  let speechActive = false;
  let silenceChunks = 0;
  let prefixBuffer = [];

  // ---- Playback state ----
  let playbackCtx = null;
  const playbackQueue = [];
  let isPlaying = false;
  let nextPlayTime = 0;
  let currentPlayback = null;

  // ------------------------------------------------------------------
  // Recording (mic → PCM16 base64 chunks)
  // ------------------------------------------------------------------

  async function _ensureMicCapture() {
    if (setupPromise) return setupPromise;
    if (audioCtx && mediaStream && workletNode) return;

    setupPromise = (async () => {
      audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });

      // Register worklet for PCM capture
      const workletCode = `
        const CHUNK_SIZE = ${CHUNK_SIZE};
        class PCMProcessor extends AudioWorkletProcessor {
          constructor() {
            super();
            this.chunk = new Int16Array(CHUNK_SIZE);
            this.offset = 0;
            this.squareSum = 0;
            this.peak = 0;
          }

          process(inputs) {
            const input = inputs[0];
            if (input && input[0]) {
              const float32 = input[0];
              for (let i = 0; i < float32.length; i++) {
                const s = Math.max(-1, Math.min(1, float32[i]));
                this.chunk[this.offset++] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                this.squareSum += s * s;
                this.peak = Math.max(this.peak, Math.abs(s));

                if (this.offset >= CHUNK_SIZE) {
                  const out = this.chunk;
                  this.port.postMessage({
                    buffer: out.buffer,
                    rms: Math.sqrt(this.squareSum / CHUNK_SIZE),
                    peak: this.peak,
                  }, [out.buffer]);
                  this.chunk = new Int16Array(CHUNK_SIZE);
                  this.offset = 0;
                  this.squareSum = 0;
                  this.peak = 0;
                }
              }
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
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      sourceNode = audioCtx.createMediaStreamSource(mediaStream);
      workletNode = new AudioWorkletNode(audioCtx, "pcm-processor");

      workletNode.port.onmessage = (event) => {
        if (isRecording.value && onAudioChunk) {
          _handleRecordedChunk(event.data);
        }
      };

      sourceNode.connect(workletNode);
      workletNode.connect(audioCtx.destination); // needed to keep processing
      isMicReady.value = true;
    })().finally(() => {
      setupPromise = null;
    });

    return setupPromise;
  }

  async function startRecording(chunkCallback) {
    const requestId = ++recordingRequestId;
    _configureRecordingCallbacks(chunkCallback);
    await _ensureMicCapture();
    if (requestId !== recordingRequestId) return;

    if (audioCtx?.state === "suspended") {
      await audioCtx.resume();
    }
    _resetSpeechGate();
    isRecording.value = true;
  }

  function stopRecording() {
    recordingRequestId += 1;
    isRecording.value = false;
  }

  function disposeRecording() {
    stopRecording();
    if (workletNode) {
      workletNode.disconnect();
      workletNode = null;
    }
    if (sourceNode) {
      sourceNode.disconnect();
      sourceNode = null;
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
    onSpeechStart = null;
    onSpeechEnd = null;
    shouldStartSpeech = null;
    gateSilence = true;
    isMicReady.value = false;
    _resetSpeechGate();
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

  function enqueue(base64pcm, metadata = {}) {
    const ctx = _ensurePlaybackCtx();
    const raw = atob(base64pcm);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 0x8000;
    }

    const buffer = ctx.creat