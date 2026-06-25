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
        :disabled="store.connectionStatus !== 'connected'"
        @pointerdown.prevent="handlePointerDown"
        @pointerup.prevent="endPushToTalk"
        @pointercancel.prevent="endPushToTalk"
        @pointerleave.prevent="endPushToTalk"
      >
        {{ audio.isRecording.value ? "Recording..." : "Hold Space / Mic" }}
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
const audio = useAudio();
const ws = useWebSocket({ enqueue: audio.enqueue, flush: audio.flush, stop: audio.stop });

let sessionPromise = null;
let isStartingPushToTalk = false;
let pushToTalkRequestId = 0;
let sentAudioThisTurn = false;

const statusClass = computed(() => ({
  "status-dot--connected": store.connectionStatus === "connected",
  "status-dot--connecting": store.connectionStatus === "connecting",
  "status-dot--disconnected": store.connectionStatus === "disconnected",
}));

// Connect backend WS on mount → get views immediately
onMounted(() => {
  ws.connect();
  window.addEventListener("keydown", handleKeyDown);
  window.addEventListener("keyup", handleKeyUp);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeyDown);
  window.removeEventListener("keyup", handleKeyUp);
});

async function ensureSessionReady() {
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

async function beginPushToTalk() {
  if (isStartingPushToTalk || audio.isRecording.value || store.connectionStatus !== "connected") return;

  const requestId = ++pushToTalkRequestId;
  isStartingPushToTalk = true;
  await ensureSessionReady();
  if (requestId !== pushToTalkRequestId || store.connectionStatus !== "connected") {
    if (requestId === pushToTalkRequestId) {
      isStartingPushToTalk = false;
    }
    return;
  }

  sentAudioThisTurn = false;
  ws.beginPushToTalk();
  audio.stop();
  try {
    await audio.startRecording((base64pcm) => {
      sentAudioThisTurn = true;
      ws.sendAudio(base64pcm);
    });
  } catch (error) {
    console.error("Failed to start push-to-talk recording:", error);
    audio.stopRecording();
  } finally {
    if (requestId === pushToTalkRequestId) {
      isStartingPushToTalk = false;
    }
  }
}

function endPushToTalk() {
  const wasRecording = audio.isRecording.value;

  audio.stopRecording();
  pushToTalkRequestId += 1;
  isStartingPushToTalk = false;
  if (wasRecording && sentAudioThisTurn) {
    ws.commitAudio();
  }
  sentAudioThisTurn = false;
}

function handlePointerDown(event) {
  event.currentTarget.setPointerCapture?.(event.pointerId);
  beginPushToTalk();
}

function handleKeyDown(event) {
  if (event.code !== "Space" || event.repeat || shouldIgnoreShortcut(event.target)) return;
  event.preventDefault();
  beginPushToTalk();
}

function handleKeyUp(event) {
  if (event.code !== "Space" || shouldIgnoreShortcut(event.target)) return;
  event.preventDefault();
  endPushToTalk();
}

function shouldIgnoreShortcut(target) {
  const tagName = target?.tagName?.toLowerCase();
  return tagName === "input" || tagName === "textarea" || target?.isContentEditable;
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
