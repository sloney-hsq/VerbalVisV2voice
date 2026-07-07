import { ref, onBeforeUnmount } from "vue";

const DEFAULT_INPUT_SAMPLE_RATE = 16000; // Qwen realtime input rate
const DEFAULT_OUTPUT_SAMPLE_RATE = 24000;
const CHUNK_MS = 40;
const PREFIX_CHUNKS = 3;
const TRAILING_SILENCE_CHUNKS = 9;
const SPEECH_RMS_THRESHOLD = 0.01;
const SILENCE_RMS_THRESHOLD = 0.006;
const SPEECH_CONFIRM_CHUNKS = 3;

/**
 * Audio composable – handles microphone capture and PCM16 playback.
 */
export function useAudio(options = {}) {
  const inputSampleRate = Number(options.inputSampleRate) || DEFAULT_INPUT_SAMPLE_RATE;
  const outputSampleRate = Number(options.outputSampleRate) || DEFAULT_OUTPUT_SAMPLE_RATE;
  const chunkSize = Math.round((inputSampleRate * CHUNK_MS) / 1000);

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
  let speechCandidateChunks = 0;
  let speechCandidateMaxRms = 0;
  let speechCandidateMaxPeak = 0;

  // ---- Playback state ----
  let playbackCtx = null;
  let playbackGainNode = null;
  const activeSources = new Set();
  const invalidatedResponseIds = new Set();
  let assistantAudioBlocked = false;
  let currentPlaybackResponseId = null;
  let nextPlayTime = 0;
  let currentPlayback = null;
  let onPlaybackIdle = null;

  // ------------------------------------------------------------------
  // Recording (mic → PCM16 base64 chunks)
  // ------------------------------------------------------------------

  async function _ensureMicCapture() {
    if (setupPromise) return setupPromise;
    if (audioCtx && mediaStream && workletNode) return;

    setupPromise = (async () => {
      audioCtx = new AudioContext({ sampleRate: inputSampleRate });

      // Register worklet for PCM capture
      const workletCode = `
        const CHUNK_SIZE = ${chunkSize};
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
          sampleRate: inputSampleRate,
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
      playbackCtx = new AudioContext({ sampleRate: outputSampleRate });
      playbackGainNode = playbackCtx.createGain();
      playbackGainNode.gain.value = 1;
      playbackGainNode.connect(playbackCtx.destination);
    } else if (!playbackGainNode) {
      playbackGainNode = playbackCtx.createGain();
      playbackGainNode.gain.value = 1;
      playbackGainNode.connect(playbackCtx.destination);
    }
    return playbackCtx;
  }

  function enqueue(base64pcm, metadata = {}) {
    const responseId = metadata?.response_id || metadata?.responseId || null;
    if (assistantAudioBlocked) return false;
    if (responseId && invalidatedResponseIds.has(responseId)) return false;
    if (responseId && currentPlaybackResponseId && responseId !== currentPlaybackResponseId) {
      stopAssistantAudio({ responseId: currentPlaybackResponseId });
    }
    if (responseId) {
      currentPlaybackResponseId = responseId;
    }

    const ctx = _ensurePlaybackCtx();
    const raw = atob(base64pcm);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 0x8000;
    }

    const buffer = ctx.createBuffer(1, float32.length, outputSampleRate);
    buffer.getChannelData(0).set(float32);

    const now = ctx.currentTime;
    if (nextPlayTime < now) nextPlayTime = now;
    const scheduledStart = nextPlayTime;

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(playbackGainNode || ctx.destination);
    const sourceRecord = {
      source,
      responseId,
      itemId: metadata?.item_id || metadata?.itemId || null,
      stopped: false,
    };
    activeSources.add(sourceRecord);
    source.onended = () => {
      if (sourceRecord.stopped) return;
      activeSources.delete(sourceRecord);
      if (activeSources.size === 0) {
        const completedResponseId = currentPlaybackResponseId || currentPlayback?.responseId || responseId;
        currentPlayback = null;
        currentPlaybackResponseId = null;
        onPlaybackIdle?.({ responseId: completedResponseId });
      }
    };
    source.start(scheduledStart);
    nextPlayTime += buffer.duration;
    _trackPlayback(metadata, scheduledStart, buffer.duration);
    return true;
  }

  function flush(metadata = {}) {
    const responseId = metadata?.response_id || metadata?.responseId || null;
    if (
      !metadata ||
      !responseId ||
      currentPlayback?.responseId === responseId
    ) {
      currentPlayback = null;
    }
  }

  function beginAssistantResponse(responseId) {
    if (!responseId) return;
    assistantAudioBlocked = false;
    invalidatedResponseIds.delete(responseId);
    currentPlaybackResponseId = responseId;
    if (playbackCtx?.state === "suspended") {
      playbackCtx.resume().catch(() => {});
    }
  }

  function stop() {
    const cursor = getPlaybackCursor();
    stopAssistantAudio({});
    return cursor;
  }

  async function pauseAssistantAudio({ responseId = null } = {}) {
    if (responseId && currentPlaybackResponseId && responseId !== currentPlaybackResponseId) return;
    if (playbackCtx && playbackCtx.state === "running") {
      await playbackCtx.suspend();
    }
  }

  async function resumeAssistantAudio({ responseId = null } = {}) {
    if (responseId && currentPlaybackResponseId && responseId !== currentPlaybackResponseId) return;
    assistantAudioBlocked = false;
    if (playbackCtx && playbackCtx.state === "suspended") {
      await playbackCtx.resume();
    }
  }

  function stopAssistantAudio({ responseId = null, blockNewAudio = false } = {}) {
    if (blockNewAudio) assistantAudioBlocked = true;
    if (playbackCtx?.state === "suspended") {
      playbackCtx.resume().catch(() => {});
    }

    if (responseId) {
      invalidatedResponseIds.add(responseId);
    } else {
      for (const record of activeSources) {
        if (record.responseId) invalidatedResponseIds.add(record.responseId);
      }
      if (currentPlayback?.responseId) {
        invalidatedResponseIds.add(currentPlayback.responseId);
      }
    }

    for (const record of Array.from(activeSources)) {
      if (!responseId || record.responseId === responseId) {
        try {
          record.stopped = true;
          record.source.stop();
        } catch (_) {
          // Already ended.
        }
        activeSources.delete(record);
      }
    }

    if (
      !responseId ||
      currentPlayback?.responseId === responseId
    ) {
      nextPlayTime = playbackCtx && playbackCtx.state !== "closed" ? playbackCtx.currentTime : 0;
      currentPlayback = null;
    }
    if (!responseId || currentPlaybackResponseId === responseId) {
      currentPlaybackResponseId = null;
    }
  }

  function allowAssistantAudio() {
    assistantAudioBlocked = false;
  }

  function setPlaybackIdleHandler(callback) {
    onPlaybackIdle = typeof callback === "function" ? callback : null;
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

  function _configureRecordingCallbacks(callbackConfig) {
    onSpeechStart = null;
    onSpeechEnd = null;
    shouldStartSpeech = null;
    gateSilence = true;

    if (typeof callbackConfig === "function") {
      onAudioChunk = callbackConfig;
      return;
    }

    onAudioChunk = callbackConfig?.onChunk || null;
    onSpeechStart = callbackConfig?.onSpeechStart || null;
    onSpeechEnd = callbackConfig?.onSpeechEnd || null;
    shouldStartSpeech = callbackConfig?.shouldStartSpeech || null;
    gateSilence = callbackConfig?.gateSilence !== false;
  }

  function _trackPlayback(metadata, scheduledStart, duration) {
    const itemId = metadata?.item_id || metadata?.itemId;
    const responseId = metadata?.response_id || metadata?.responseId || null;
    if (!itemId) return;

    const contentIndex = metadata?.content_index ?? metadata?.contentIndex ?? 0;
    if (
      !currentPlayback ||
      currentPlayback.itemId !== itemId ||
      currentPlayback.contentIndex !== contentIndex
    ) {
      currentPlayback = {
        itemId,
        responseId,
        contentIndex,
        startTime: scheduledStart,
        endTime: scheduledStart,
      };
    }
    currentPlayback.endTime = Math.max(currentPlayback.endTime, scheduledStart + duration);
  }

  function getPlaybackCursor() {
    if (!playbackCtx || playbackCtx.state === "closed" || !currentPlayback?.itemId) {
      return null;
    }
    const elapsedMs = Math.max(
      0,
      Math.min(
        (currentPlayback.endTime - currentPlayback.startTime) * 1000,
        (playbackCtx.currentTime - currentPlayback.startTime) * 1000
      )
    );
    return {
      item_id: currentPlayback.itemId,
      content_index: currentPlayback.contentIndex,
      audio_end_ms: Math.round(elapsedMs),
    };
  }

  function _handleRecordedChunk(chunk) {
    const buffer = chunk.buffer || chunk;
    const rms = chunk.rms ?? 0;
    const base64 = _arrayBufferToBase64(buffer);

    if (!gateSilence) {
      _updateUngatedSpeechActivity(rms, chunk.peak ?? 0);
      onAudioChunk?.(base64);
      return;
    }

    if (!speechActive) {
      prefixBuffer.push(buffer);
      if (prefixBuffer.length > PREFIX_CHUNKS) {
        prefixBuffer.shift();
      }
      const speechStart = _confirmedSpeechStart(rms, chunk.peak ?? 0);
      if (speechStart) {
        if (shouldStartSpeech && !shouldStartSpeech(speechStart)) {
          prefixBuffer = [];
          _resetSpeechCandidate();
          return;
        }
        speechActive = true;
        silenceChunks = 0;
        onSpeechStart?.(speechStart);
        prefixBuffer.forEach((buf) => onAudioChunk?.(_arrayBufferToBase64(buf)));
        prefixBuffer = [];
      }
      return;
    }

    onAudioChunk?.(base64);
    if (rms < SILENCE_RMS_THRESHOLD) {
      silenceChunks += 1;
      if (silenceChunks >= TRAILING_SILENCE_CHUNKS) {
        speechActive = false;
        silenceChunks = 0;
        prefixBuffer = [];
        _resetSpeechCandidate();
        onSpeechEnd?.();
      }
    } else {
      silenceChunks = 0;
    }
  }

  function _resetSpeechGate() {
    speechActive = false;
    silenceChunks = 0;
    prefixBuffer = [];
    _resetSpeechCandidate();
  }

  function _updateUngatedSpeechActivity(rms, peak) {
    if (!speechActive) {
      const speechStart = _confirmedSpeechStart(rms, peak);
      if (speechStart) {
        if (shouldStartSpeech && !shouldStartSpeech(speechStart)) {
          _resetSpeechCandidate();
          return;
        }
        speechActive = true;
        silenceChunks = 0;
        onSpeechStart?.(speechStart);
      }
      return;
    }

    if (rms < SILENCE_RMS_THRESHOLD) {
      silenceChunks += 1;
      if (silenceChunks >= TRAILING_SILENCE_CHUNKS) {
        speechActive = false;
        silenceChunks = 0;
        _resetSpeechCandidate();
        onSpeechEnd?.();
      }
    } else {
      silenceChunks = 0;
    }
  }

  function _confirmedSpeechStart(rms, peak) {
    if (rms < SPEECH_RMS_THRESHOLD) {
      _resetSpeechCandidate();
      return null;
    }

    speechCandidateChunks += 1;
    speechCandidateMaxRms = Math.max(speechCandidateMaxRms, rms);
    speechCandidateMaxPeak = Math.max(speechCandidateMaxPeak, peak);

    if (speechCandidateChunks < SPEECH_CONFIRM_CHUNKS) return null;

    return {
      rms: speechCandidateMaxRms,
      peak: speechCandidateMaxPeak,
      duration_ms: speechCandidateChunks * CHUNK_MS,
      chunks: speechCandidateChunks,
      threshold: SPEECH_RMS_THRESHOLD,
    };
  }

  function _resetSpeechCandidate() {
    speechCandidateChunks = 0;
    speechCandidateMaxRms = 0;
    speechCandidateMaxPeak = 0;
  }

  onBeforeUnmount(() => {
    disposeRecording();
    stop();
  });

  function getMicStream() {
    return mediaStream;
  }

  function resetSpeechGate() {
    _resetSpeechGate();
  }

  return {
    isRecording,
    isMicReady,
    startRecording,
    stopRecording,
    disposeRecording,
    getMicStream,
    getPlaybackCursor,
    resetSpeechGate,
    inputSampleRate,
    outputSampleRate,
    // Playback interface (passed to useWebSocket)
    enqueue,
    flush,
    beginAssistantResponse,
    stop,
    pauseAssistantAudio,
    resumeAssistantAudio,
    stopAssistantAudio,
    allowAssistantAudio,
    setPlaybackIdleHandler,
  };
}
