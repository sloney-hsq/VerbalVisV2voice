<template>
  <main class="dashboard">
    <!-- Header -->
    <header class="dashboard__header">
      <h1 class="dashboard__title">VerbalVis</h1>
      <div class="dashboard__status">
        <span class="status-dot" :class="statusClass"></span>
        <span>{{ store.connectionStatus }}</span>
      </div>
    </header>

    <!-- Controls -->
    <section class="dashboard__controls">
      <button
        class="btn btn--record"
        :class="{ 'btn--recording': audio.isRecording.value }"
        :disabled="recordButtonDisabled"
        @click.prevent="handleRecordClick"
      >
        {{ recordButtonLabel }}
      </button>

      <!-- Filter badges -->
      <div v-if="store.activeFilters.length" class="filter-badges">
        <span class="filter-badge" v-for="(f, i) in store.activeFilters" :key="i">
          {{ f.field }} {{ f.operator }} {{ f.value }}
        </span>
      </div>
    </section>

    <!-- Chart Grid -->
    <section class="dashboard__grid">
      <ChartSlot v-for="view in store.views" :key="view.id" :view="view" />
    </section>

    <!-- Transcript -->
    <section v-if="store.transcripts.length" class="dashboard__transcript">
      <h3>Conversation</h3>
      <div class="transcript-list">
        <div
          v-for="(t, i) in store.transcripts"
          :key="i"
          class="transcript-item"
          :class="'transcript-item--' + t.role"
        >
          <strong>{{ t.role === 'user' ? 'You' : 'AI' }}:</strong>
          {{ t.text }}
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from "vue";
import ChartSlot from "./ChartSlot.vue";
import { useDashboardStore } from "../stores/dashboard";
import { useAudio } from "../composables/useAudio";
import { useWebSocket } from "../composables/useWebSocket";

const store = useDashboardStore();
const QWEN_REALTIME_MODEL = "qwen3.5-omni-plus-realtime";
const realtimeInputSampleRate = getNumericOption(
  "inputRate",
  "VITE_REALTIME_INPUT_SAMPLE_RATE",
  16000
);
const realtimeOutputSampleRate = getNumericOption(
  "outputRate",
  "VITE_REALTIME_OUTPUT_SAMPLE_RATE",
  24000
);
const audio = useAudio({
  inputSampleRate: realtimeInputSampleRate,
  outputSampleRate: realtimeOutputSampleRate,
});
const ws = useWebSocket({ enqueue: audio.enqueue, flush: audio.flush, stop: audio.stop });

let sessionPromise = null;
let isStartingListening = false;
let sentAudioThisTurn = false;
let localInterruptArmed = false;

const statusClass = computed(() => ({
  "status-dot--connected": store.connectionStatus === "connected",
  "status-dot--connecting": store.connectionStatus === "connecting",
  "status-dot--disconnected": store.connectionStatus === "disconnected",
}));

const recordButtonDisabled = computed(() => (
  store.connectionStatus !== "connected" ||
  (store.sessionMode === "turn_based" && store.isAssistantSpeaking)
));

const recordButtonLabel = computed(() => {
  if (store.isAssistantSpeaking && store.sessionMode !== "turn_based") {
    return "Interrupt";
  }
  return audio.isRecording.value ? "Listening..." : "Start Mic";
});

// Connect backend WS on mount → get views immediately
onMounted(() => {
  ws.connect(buildRealtimeWsUrl());
  window.addEventListener("keydown", handleKeyDown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeyDown);
});

async function ensureSessionReady({ fresh = false } = {}) {
  if (fresh) {
    sessionPromise = null;
    store.sessionReady = false;
    await waitForSocketOpen();
  }
  if (store.sessionReady) return;
  if (sessionPromise) return sessionPromise;

  sessionPromise = new Promise((resolve) => {
    ws.startSession();
    const check = setInterval(() => {
      if (store.sessionReady) {
        clearInterval(check);
        sessionPromise = null;
        resolve();
      }
    }, 100);
    setTimeout(() => {
      clearInterval(check);
      sessionPromise = null;
      resolve();
    }, 15000);
  });

  return sessionPromise;
}

function waitForSocketOpen(timeoutMs = 5000) {
  const start = Date.now();
  return new Promise((resolve) => {
    const check = setInterval(() => {
      if (ws.socket.value?.readyState === WebSocket.OPEN || Date.now() - start >= timeoutMs) {
        clearInterval(check);
        resolve();
      }
    }, 50);
  });
}

async function startListeningMic() {
  if (isStartingListening || audio.isRecording.value || recordButtonDisabled.value) {
    return;
  }

  isStartingListening = true;
  await ensureSessionReady({ fresh: true });
  if (recordButtonDisabled.value) {
    isStartingListening = false;
    return;
  }

  sentAudioThisTurn = false;
  try {
    await audio.startRecording({
      gateSilence: store.inputMode !== "open_mic",
      shouldStartSpeech: () => (
        store.inputMode !== "local_vad" ||
        !store.isAssistantSpeaking
      ),
      onSpeechStart: handleLocalSpeechStart,
      onSpeechEnd: handleLocalSpeechEnd,
      onChunk: (base64pcm) => {
        if (
          store.isAssistantSpeaking &&
          (store.inputMode === "local_vad" || store.sessionMode === "turn_based")
        ) {
          return;
        }
        sentAudioThisTurn = true;
        ws.sendAudio(base64pcm);
      },
    });
  } catch (error) {
    console.error("Failed to start microphone listening:", error);
    audio.stopRecording();
  } finally {
    isStartingListening = false;
  }
}

function stopListeningMic() {
  const wasRecording = audio.isRecording.value;
  audio.stopRecording();
  isStartingListening = false;
  localInterruptArmed = false;
  if (wasRecording && store.inputMode === "local_vad" && sentAudioThisTurn) {
    ws.commitAudio();
  }
  sentAudioThisTurn = false;
}

function handleLocalSpeechStart() {
  if (store.inputMode !== "local_vad") return;
  if (store.isAssistantSpeaking) return;

  sentAudioThisTurn = false;
  if (localInterruptArmed) {
    localInterruptArmed = false;
    return;
  }
}

function handleLocalSpeechEnd() {
  if (store.inputMode !== "local_vad") return;
  if (sentAudioThisTurn) {
    ws.commitAudio();
  }
  sentAudioThisTurn = false;
}

function handleRecordClick() {
  if (store.inputMode === "local_vad" && store.isAssistantSpeaking) {
    interruptAssistantForLocalVad();
    return;
  }
  if (audio.isRecording.value) {
    stopListeningMic();
  } else {
    startListeningMic();
  }
}

async function interruptAssistantForLocalVad() {
  if (store.sessionMode === "turn_based") return;
  await ensureSessionReady();
  const assistantAudio = audio.stop();
  audio.resetSpeechGate();
  store.isAssistantSpeaking = false;
  sentAudioThisTurn = false;
  localInterruptArmed = true;
  ws.truncateAssistantAudio(assistantAudio);
  if (!audio.isRecording.value) {
    startListeningMic();
  }
}

function handleKeyDown(event) {
  if (event.code !== "Space" || event.repeat || shouldIgnoreShortcut(event.target)) return;
  event.preventDefault();
  handleRecordClick();
}

function shouldIgnoreShortcut(target) {
  const tagName = target?.tagName?.toLowerCase();
  return tagName === "input" || tagName === "textarea" || target?.isContentEditable;
}

function getNumericOption(queryKey, envKey, fallback) {
  const params = new URLSearchParams(window.location.search);
  const value = Number(params.get(queryKey) || import.meta.env[envKey]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function buildRealtimeWsUrl() {
  const params = new URLSearchParams(window.location.search);
  const explicitUrl = params.get("ws") || import.meta.env.VITE_REALTIME_WS_URL;
  if (explicitUrl) return explicitUrl;

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const configuredPath = (
    params.get("wsPath") ||
    import.meta.env.VITE_REALTIME_WS_PATH ||
    "/ws"
  );
  const path = configuredPath.startsWith("/") ? configuredPath : `/${configuredPath}`;
  const url = new URL(`${protocol}://${window.location.host}${path}`);
  url.searchParams.set("model", QWEN_REALTIME_MODEL);

  return url.toString();
}
</script>

<style scoped>
.dashboard {
  padding: 20px;
  max-width: 1600px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.dashboard__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.dashboard__title {
  font-size: 22px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}

.dashboard__status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #6b7280;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #9ca3af;
}
.status-dot--connected { background: #22c55e; }
.status-dot--connecting { background: #eab308; }
.status-dot--disconnected { background: #9ca3af; }

.dashboard__controls {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.btn {
  padding: 6px 14px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
}
.btn:hover { background: #f3f4f6; }
.btn--primary { background: #3b82f6; color: #fff; border-color: #3b82f6; }
.btn--primary:hover { background: #2563eb; }
.btn--record { background: #ef4444; color: #fff; border-color: #ef4444; }
.btn--record:hover { background: #dc2626; }
.btn--record:disabled { background: #9ca3af; border-color: #9ca3af; cursor: not-allowed; }
.btn--recording { background: #991b1b; border-color: #991b1b; }

.filter-badges {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.filter-badge {
  background: #eef2ff;
  color: #4338ca;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-family: monospace;
}

.dashboard__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 16px;
}

.dashboard__transcript {
  margin-top: 24px;
  border-top: 1px solid #e5e7eb;
  padding-top: 12px;
}
.dashboard__transcript h3 {
  font-size: 14px;
  color: #6b7280;
  margin: 0 0 8px;
}
.transcript-list {
  max-height: 200px;
  overflow-y: auto;
  font-size: 13px;
}
.transcript-item {
  padding: 4px 0;
  border-bottom: 1px solid #f3f4f6;
}
.transcript-item--user { color: #1d4ed8; }
.transcript-item--assistant { color: #374151; }
</style>
