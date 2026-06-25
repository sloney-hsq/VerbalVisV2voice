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
        @pointerdown.prevent="handlePointerDown"
        @pointerup.prevent="endPushToTalk"
        @pointercancel.prevent="endPushToTalk"
        @pointerleave.prevent="endPushToTalk"
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
const audio = useAudio();
const ws = useWebSocket({ enqueue: audio.enqueue, flush: audio.flush, stop: audio.stop });

let sessionPromise = null;
let isStartingPushToTalk = false;
let isStartingListening = false;
let pushToTalkRequestId = 0;
let sentAudioThisTurn = false;
let localInterruptArmed = false;

const statusClass = computed(() => ({
  "status-dot--connected": store.connectionStatus === "connected",
  "status-dot--connecting": store.connectionStatus === "connecting",
  "status-dot--disconnected": store.connectionStatus === "disconnected",
}));

const usesToggleMic = computed(() => store.inputMode !== "push_to_talk");

const recordButtonDisabled = computed(() => (
  store.connectionStatus !== "connected" ||
  (store.sessionMode === "turn_based" && store.isAssistantSpeaking)
));

const recordButtonLabel = computed(() => {
  if (store.inputMode === "push_to_talk") {
    return audio.isRecording.value ? "Recording..." : "Hold Space / Mic";
  }
  if (store.inputMode === "open_mic") {
    return audio.isRecording.value ? "Open Mic On" : "Start Open Mic";
  }
  if (store.isAssistantSpeaking && store.sessionMode !== "turn_based") {
    return "Interrupt";
  }
  return audio.isRecording.value ? "Listening..." : "Start Mic";
});

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
  if (
    usesToggleMic.value ||
    isStartingPushToTalk ||
    audio.isRecording.value ||
    recordButtonDisabled.value
  ) return;

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
  const assistantAudio = audio.stop();
  ws.beginPushToTalk(assistantAudio);
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
  if (usesToggleMic.value) return;
  const wasRecording = audio.isRecording.value;

  audio.stopRecording();
  pushToTalkRequestId += 1;
  isStartingPushToTalk = false;
  if (wasRecording && sentAudioThisTurn) {
    ws.commitAudio();
  }
  sentAudioThisTurn = false;
}

async function startListeningMic() {
  if (!usesToggleMic.value || isStartingListening || audio.isRecording.value || recordButtonDisabled.value) {
    return;
  }

  isStartingListening = true;
  await ensureSessionReady();
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
  const assistantAudio = audio.stop();
  ws.beginPushToTalk(assistantAudio);
}

function handleLocalSpeechEnd() {
  if (store.inputMode !== "local_vad") return;
  if (sentAudioThisTurn) {
    ws.commitAudio();
  }
  sentAudioThisTurn = false;
}

function handleRecordClick() {
  if (!usesToggleMic.value) return;
  if (store.inputMode === "local_vad" && store.isAssistantSpeaking) {
    interruptAssistantForLocalVad();
    return;
  }
  if (audio.isRecording.value) {
    stopListeningMic();