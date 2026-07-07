<template>
  <main class="dashboard">
    <header class="dashboard__topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="brand-copy">
          <h1 class="dashboard__title">VerbalVis</h1>
          <p>Hands-Free EDA with Speech</p>
        </div>
      </div>

      <div class="model-status" :title="modelStatusTitle">
        <span class="status-dot" :class="statusClass"></span>
        <span class="model-status__model">{{ displayModelName }}</span>
        <span class="model-status__state">{{ connectionLabel }}</span>

        <div v-if="store.activeFilters.length" class="status-filters" aria-label="Global filters">
          <span class="status-filters__label">Global filters</span>
          <span class="status-filter" v-for="(f, i) in store.activeFilters" :key="i">
            {{ filterLabel(f) }}
          </span>
        </div>

        <div v-if="store.recentToolCalls.length" class="tool-call-strip" aria-label="Recent tool calls">
          <span
            v-for="tool in store.recentToolCalls"
            :key="tool.id"
            class="tool-call-chip"
            :title="toolCallTitle(tool)"
          >
            <svg class="tool-call-chip__icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M14.7 6.3a4.5 4.5 0 0 0-5.7 5.7L4 17v3h3l5-5a4.5 4.5 0 0 0 5.7-5.7l-2.6 2.6-2-2 2.6-2.6Z" />
            </svg>
            {{ formatToolName(tool.name) }}
          </span>
        </div>
      </div>

      <div class="interaction-control">
        <div class="mode-switch" aria-label="Interaction mode">
          <button
            class="mode-switch__button"
            :class="{ 'mode-switch__button--active': interactionMode === 'voice' }"
            type="button"
            title="Voice mode"
            @click="setInteractionMode('voice')"
          >
            Voice
          </button>
          <button
            class="mode-switch__button"
            :class="{ 'mode-switch__button--active': interactionMode === 'text' }"
            type="button"
            title="Text mode"
            @click="setInteractionMode('text')"
          >
            Text
          </button>
        </div>
        <button
          v-if="interactionMode === 'voice'"
          class="mic-pill"
          :class="{ 'mic-pill--recording': audio.isRecording.value }"
          :disabled="recordButtonDisabled"
          :title="recordButtonLabel"
          @click.prevent="handleRecordClick"
        >
          <span class="mic-pill__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" />
              <path d="M18 11a6 6 0 0 1-12 0" />
              <path d="M12 17v4" />
              <path d="M9 21h6" />
            </svg>
          </span>
          <span>{{ voiceStatusLabel }}</span>
        </button>
        <div
          v-else
          class="text-status"
          :class="{ 'text-status--busy': store.isTextTurnProcessing }"
        >
          {{ textTurnLabel }}
        </div>
      </div>
    </header>

    <!-- Chart Grid -->
    <section class="dashboard__grid">
      <ChartSlot v-for="view in store.views" :key="view.id" :view="view" />
    </section>

    <section
      v-if="interactionMode === 'voice'"
      class="dashboard__transcript"
      aria-label="Session transcript"
    >
      <div class="transcript-header">
        <h3>Session Transcript</h3>
        <div class="transcript-actions">
          <label class="transcript-toggle">
            <span>Auto-scroll</span>
            <input v-model="autoScrollTranscripts" type="checkbox" />
            <span class="transcript-toggle__track" aria-hidden="true"></span>
          </label>
          <button class="transcript-clear" type="button" @click="clearTranscript">
            Clear
          </button>
        </div>
      </div>

      <div ref="transcriptList" class="transcript-list" aria-live="polite">
        <div
          v-for="exchange in transcriptRows"
          :key="exchange.id"
          class="transcript-exchange"
          :class="{ 'transcript-exchange--inline': canDisplayInline(exchange) }"
        >
          <div
            v-for="message in exchangeMessages(exchange)"
            :key="message.id"
            class="transcript-message"
            :class="transcriptMessageClass(message)"
            :title="message.text"
            @click="toggleTranscriptMessage(message)"
          >
            <span class="transcript-time">{{ transcriptMessageTime(exchange, message) }}</span>
            <span class="transcript-role">{{ transcriptRoleLabel(message) }}</span>
            <span class="transcript-content">
              <span
                class="transcript-text"
                :class="{ 'transcript-text--collapsed': !message.expanded }"
              >
                {{ transcriptDisplayText(message) }}
              </span>
              <span
                v-if="message.toolActionsExpanded"
                class="transcript-tool-list"
              >
                <span
                  v-for="(action, index) in message.toolActions"
                  :key="`${message.id}-action-${index}`"
                  class="transcript-tool-item"
                >
                  {{ action.summary }}
                </span>
              </span>
            </span>
            <span class="transcript-meta">
              <button
                v-if="message.toolActions?.length"
                class="transcript-action-count"
                type="button"
                :title="toolActionsTitle(message)"
                @click.stop="toggleTranscriptActions(message)"
              >
                {{ toolActionsLabel(message) }}
              </button>
              <span
                v-if="message.status === 'interrupted'"
                class="message-status message-status--interrupted"
                title="Assistant response interrupted by the user"
              >
                x
              </span>
            </span>
          </div>
        </div>
      </div>
    </section>

    <section v-else class="dashboard__text-entry" aria-label="Text interaction">
      <div ref="textHistoryList" class="text-history" aria-live="polite">
        <div
          v-for="exchange in transcriptRows"
          :key="`text-${exchange.id}`"
          class="text-history__exchange"
        >
          <div
            v-for="message in exchangeMessages(exchange)"
            :key="`text-${message.id}`"
            class="text-history__message"
            :class="`text-history__message--${message.role}`"
            :title="message.text"
          >
            <span class="text-history__role">{{ transcriptRoleLabel(message) }}</span>
            <span class="text-history__content">
              {{ transcriptDisplayText(message) }}
              <span
                v-if="message.toolActionsExpanded"
                class="text-history__tools"
              >
                <span
                  v-for="(action, index) in message.toolActions"
                  :key="`${message.id}-text-tool-${index}`"
                  class="transcript-tool-item"
                >
                  {{ action.summary }}
                </span>
              </span>
            </span>
            <button
              v-if="message.toolActions?.length"
              class="transcript-action-count"
              type="button"
              :title="toolActionsTitle(message)"
              @click.stop="toggleTranscriptActions(message)"
            >
              {{ toolActionsLabel(message) }}
            </button>
          </div>
        </div>
      </div>
      <div v-if="pendingText" class="text-pending" aria-live="polite">
        <span class="text-pending__role">YOU</span>
        <span class="text-pending__content">{{ pendingText }}</span>
      </div>
      <form
        class="text-composer"
        @submit.prevent="submitText"
      >
        <textarea
          ref="textInput"
          v-model="inputText"
          class="text-composer__input"
          rows="2"
          spellcheck="false"
          placeholder="Type a message"
          @keydown.enter.exact="handleTextEnter"
        ></textarea>
        <button
          class="text-composer__send"
          type="submit"
          :disabled="textSendDisabled"
          :title="textSendLabel"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 12h14" />
            <path d="m13 6 6 6-6 6" />
          </svg>
          <span>{{ textSendLabel }}</span>
        </button>
      </form>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import ChartSlot from "./ChartSlot.vue";
import { useDashboardStore } from "../stores/dashboard";
import { useAudio } from "../composables/useAudio";
import { useWebSocket } from "../composables/useWebSocket";

const store = useDashboardStore();
const QWEN_REALTIME_MODEL = "qwen3.5-omni-plus-realtime";
const analysisId = getOrCreateAnalysisId();
store.setActiveWorkspace(getInitialInteractionMode());
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
const ws = useWebSocket(
  {
    enqueue: audio.enqueue,
    flush: audio.flush,
    beginAssistantResponse: audio.beginAssistantResponse,
    stop: audio.stop,
    pauseAssistantAudio: audio.pauseAssistantAudio,
    resumeAssistantAudio: audio.resumeAssistantAudio,
    stopAssistantAudio: audio.stopAssistantAudio,
  },
  { getAnalysisId: getCurrentAnalysisId }
);

let sessionPromise = null;
const isStartingListening = ref(false);
const interactionMode = ref(getInitialInteractionMode());
const inputText = ref("");
const pendingText = ref("");
const autoScrollTranscripts = ref(true);
const transcriptList = ref(null);
const textHistoryList = ref(null);
const textInput = ref(null);
const transcriptPanelWidth = ref(0);
let transcriptResizeObserver = null;

audio.setPlaybackIdleHandler?.(() => {
  store.isAssistantSpeaking = false;
});

const statusClass = computed(() => ({
  "status-dot--connected": store.connectionStatus === "connected",
  "status-dot--connecting": store.connectionStatus === "connecting",
  "status-dot--disconnected": store.connectionStatus === "disconnected",
}));

const recordButtonDisabled = computed(() => (
  interactionMode.value !== "voice" ||
  store.connectionStatus !== "connected" ||
  (store.sessionMode === "turn_based" && store.isAssistantSpeaking)
));

const recordButtonLabel = computed(() => {
  return audio.isRecording.value ? "Stop listening" : "Start mic";
});

const displayModelName = computed(() => store.model || QWEN_REALTIME_MODEL);

const connectionLabel = computed(() => {
  if (store.connectionStatus === "connected") return "connected";
  if (store.connectionStatus === "connecting") return "connecting";
  return "disconnected";
});

const modelStatusTitle = computed(() => `${displayModelName.value} ${connectionLabel.value}`);

const voiceStatusLabel = computed(() => {
  if (audio.isRecording.value) return "Listening...";
  if (isStartingListening.value) return "Starting...";
  if (store.connectionStatus === "connecting") return "Connecting...";
  if (recordButtonDisabled.value) return "offline";
  return "Start mic";
});

const textTurnLabel = computed(() => {
  if (store.connectionStatus === "connecting") return "Connecting...";
  if (store.connectionStatus !== "connected") return "Offline";
  return store.isTextTurnProcessing ? "Assistant is analyzing..." : "Your turn";
});

const textSendDisabled = computed(() => (
  interactionMode.value !== "text" ||
  store.connectionStatus !== "connected" ||
  (!inputText.value.trim() && !pendingText.value.trim())
));

const textSendLabel = computed(() => (
  pendingText.value.trim() ? "Submit" :
  store.isTextTurnProcessing ? "Interrupt" : "Send"
));

const transcriptRows = computed(() => {
  return store.transcriptExchanges.map((exchange, index) => ({
    ...exchange,
    id: exchange.id || `exchange-${index}`,
  }));
});

const transcriptScrollKey = computed(() => (
  store.transcripts
    .map((message) => `${message.id}:${message.text.length}:${message.status}:${message.expanded}`)
    .join("|")
));

watch(
  () => [transcriptScrollKey.value, audio.isRecording.value, isStartingListening.value],
  () => {
    if (!autoScrollTranscripts.value) return;
    nextTick(() => {
      if (transcriptList.value) {
        transcriptList.value.scrollTop = transcriptList.value.scrollHeight;
      }
      if (textHistoryList.value) {
        textHistoryList.value.scrollTop = textHistoryList.value.scrollHeight;
      }
    });
  }
);

// Connect backend WS on mount → get views immediately
onMounted(() => {
  ws.connect(buildWsUrl());
  window.addEventListener("keydown", handleKeyDown);
  updateTranscriptPanelWidth();
  if (typeof ResizeObserver !== "undefined" && transcriptList.value) {
    transcriptResizeObserver = new ResizeObserver(updateTranscriptPanelWidth);
    transcriptResizeObserver.observe(transcriptList.value);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeyDown);
  transcriptResizeObserver?.disconnect();
});

watch(
  interactionMode,
  async () => {
    stopListeningMic();
    audio.stopAssistantAudio?.({ blockNewAudio: true });
    store.isAssistantSpeaking = false;
    store.setTextTurnProcessing(false);
    sessionPromise = null;
    ws.disconnect();
    await nextTick();
    ws.connect(buildWsUrl({ preserveState: true }));
    if (interactionMode.value === "text") {
      focusTextInput();
    }
  }
);

watch(
  () => store.isTextTurnProcessing,
  (isProcessing, wasProcessing) => {
    if (!isProcessing && wasProcessing && interactionMode.value === "text") {
      nextTick(focusTextInput);
    }
  }
);

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
  if (isStartingListening.value || audio.isRecording.value || recordButtonDisabled.value) {
    return;
  }

  isStartingListening.value = true;
  await ensureSessionReady();
  if (recordButtonDisabled.value) {
    isStartingListening.value = false;
    return;
  }

  try {
    await audio.startRecording({
      gateSilence: false,
      onChunk: (base64pcm) => {
        if (store.isAssistantSpeaking && store.sessionMode === "turn_based") {
          return;
        }
        ws.sendAudio(base64pcm);
      },
      onSpeechStart: () => {
        ws.beginUserSpeech?.("client_vad_speech_started");
      },
      onSpeechEnd: () => {
        ws.endUserSpeech?.();
      },
    });
  } catch (error) {
    console.error("Failed to start microphone listening:", error);
    audio.stopRecording();
  } finally {
    isStartingListening.value = false;
  }
}

function stopListeningMic() {
  audio.stopRecording();
  ws.endUserSpeech?.();
  isStartingListening.value = false;
}

function handleRecordClick() {
  if (audio.isRecording.value) {
    stopListeningMic();
  } else {
    startListeningMic();
  }
}

function handleKeyDown(event) {
  if (interactionMode.value !== "voice") return;
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

function formatToolName(name) {
  return String(name || "tool").replace(/_/g, " ");
}

function toolCallTitle(tool) {
  const args = tool?.arguments ? ` ${tool.arguments}` : "";
  return `${formatToolName(tool?.name)}${args}`;
}

function formatTranscriptTime(ts) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(ts || Date.now()));
}

function exchangeMessages(exchange) {
  return [exchange.user, exchange.assistant].filter(Boolean);
}

function canDisplayInline(exchange) {
  if (transcriptPanelWidth.value < 420 || !exchange.user || !exchange.assistant) return false;
  return (
    exchange.user.status === "completed" &&
    exchange.assistant.status === "completed" &&
    exchange.assistant.status !== "interrupted" &&
    exchange.assistant.status !== "error" &&
    visibleLength(exchange.user.text) <= 18 &&
    visibleLength(exchange.assistant.text) <= 32
  );
}

function visibleLength(value) {
  return Array.from(String(value || "").trim()).length;
}

function transcriptMessageClass(message) {
  return {
    [`transcript-message--${message.role}`]: true,
    "transcript-message--interrupted": message.status === "interrupted",
    "transcript-message--streaming": message.status === "streaming",
  };
}

function transcriptMessageTime(exchange, message) {
  if (message.role === "assistant" && exchange.user) return "";
  return formatTranscriptTime(message.startedAt || message.ts);
}

function transcriptRoleLabel(message) {
  return message.role === "assistant" ? "AI" : "YOU";
}

function transcriptDisplayText(message) {
  if (message.text) return message.text;
  if (message.status === "listening") return "Listening...";
  if (message.status === "streaming") return "...";
  return "";
}

function toggleTranscriptMessage(message) {
  if (!message?.text) return;
  store.toggleTranscriptMessage(message.id);
}

function toggleTranscriptActions(message) {
  store.toggleTranscriptActions(message.id);
}

function toolActionsLabel(message) {
  const count = message.toolActions?.length || 0;
  return `${count} action${count === 1 ? "" : "s"}`;
}

function toolActionsTitle(message) {
  return (message.toolActions || []).map((action) => action.summary).join("\n");
}

function updateTranscriptPanelWidth() {
  transcriptPanelWidth.value = transcriptList.value?.clientWidth || 0;
}

function filterLabel(filter) {
  return `${fieldLabel(filter.field)} ${operatorLabel(filter.operator)} ${formatValue(filter.value)}`;
}

function fieldLabel(field) {
  const labels = {
    order_month: "Month",
    order_week: "Week",
    order_date: "Date",
    order_dow: "Day of week",
    order_hour: "Hour",
    review_score: "Review score",
    review_bucket: "Review bucket",
    default_is_low_score: "Default low score",
    is_high_score: "High score",
    customer_state: "State",
    product_category: "Category",
    delivery_days: "Delivery days",
    estimated_delivery_days: "Estimated delivery days",
    delivery_delay_days: "Delay days",
    delivery_speed_bucket: "Delivery speed",
    is_late: "Late",
    delivery_status_bucket: "Delivery status",
    delay_bucket: "Delay bucket",
    revenue: "Revenue",
    order_item_revenue: "Item revenue",
    revenue_bucket: "Revenue bucket",
    item_count: "Item count",
    product_count: "Product count",
    category_count: "Category count",
    seller_count: "Seller count",
    freight_total: "Freight",
    avg_item_price: "Avg item price",
    freight_ratio: "Freight ratio",
    freight_bucket: "Freight bucket",
    order_size_bucket: "Order size",
    primary_payment_type: "Payment type",
    payment_method_count: "Payment method count",
    max_payment_installments: "Max installments",
    primary_payment_installments: "Primary installments",
    order_count: "Orders",
    low_score_ratio: "Low score ratio",
    late_ratio: "Late ratio",
    on_time_ratio: "On-time ratio",
    high_score_ratio: "High score ratio",
    avg_freight_ratio: "Avg freight ratio",
    state_revenue: "State revenue",
  };
  return labels[field] || field;
}

function operatorLabel(operator) {
  const labels = {
    eq: "=",
    neq: "!=",
    in: "in",
    gte: ">=",
    lte: "<=",
    between: "between",
  };
  return labels[operator] || operator;
}

function formatValue(value) {
  if (Array.isArray(value)) return value.join(", ");
  return value ?? "";
}

function clearTranscript() {
  store.clearTranscripts();
}

function submitText() {
  const text = inputText.value.trim();
  if (textSendDisabled.value) return;

  if (pendingText.value.trim() && !text) {
    submitPendingText();
    return;
  }

  if (store.isTextTurnProcessing) {
    if (text) {
      sendTextToAssistant(text);
      return;
    }
    return;
  }

  const textToSend = text || pendingText.value.trim();
  if (!textToSend) return;
  pendingText.value = "";
  sendTextToAssistant(textToSend);
}

function submitPendingText() {
  const text = pendingText.value.trim();
  if (!text) return;
  pendingText.value = "";
  sendTextToAssistant(text);
}

function sendTextToAssistant(text) {
  if (store.isTextTurnProcessing) {
    ws.interruptActiveResponse?.("user_superseded_response");
  }
  const turnId = ws.sendText(text);
  if (!turnId) {
    pendingText.value = text;
    return;
  }

  store.completeUserTranscript(text, { utteranceId: turnId });
  store.setTextTurnProcessing(true);
  inputText.value = "";
  pendingText.value = "";
  nextTick(focusTextInput);
}

function handleTextEnter(event) {
  event.preventDefault();
  submitText();
}

function focusTextInput() {
  textInput.value?.focus?.();
}

function setInteractionMode(mode) {
  if (interactionMode.value === mode) return;
  interactionMode.value = mode;
  store.setActiveWorkspace(mode);
  const url = new URL(window.location.href);
  url.searchParams.set(
    "condition",
    mode === "text" ? "turn_based_text" : "full_duplex_voice"
  );
  window.history.replaceState(null, "", url);
}

function getInitialInteractionMode() {
  const params = new URLSearchParams(window.location.search);
  const value = (params.get("condition") || params.get("mode") || "").toLowerCase();
  return ["text", "tbc", "turn_based_text", "turn-based-text"].includes(value)
    ? "text"
    : "voice";
}

function getOrCreateAnalysisId() {
  const params = new URLSearchParams(window.location.search);
  const explicit = normalizeAnalysisId(params.get("analysis_id") || params.get("analysisId"));
  if (explicit) {
    return setCurrentAnalysisId(explicit);
  }

  const existing = normalizeAnalysisId(window.__verbalvis_analysis_id);
  if (existing) return existing;

  const id = `session-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 10)}`;
  return setCurrentAnalysisId(id);
}

function normalizeAnalysisId(value) {
  return String(value || "").trim().replace(/[^A-Za-z0-9_.-]/g, "-").slice(0, 80);
}

function setCurrentAnalysisId(id) {
  window.__verbalvis_analysis_id = id;
  return id;
}

function getCurrentAnalysisId() {
  return `${analysisId}-${interactionMode.value === "text" ? "text" : "voice"}`;
}

function buildWsUrl({ preserveState = false } = {}) {
  const params = new URLSearchParams(window.location.search);
  const explicitUrl = interactionMode.value === "text"
    ? (params.get("textWs") || import.meta.env.VITE_TEXT_WS_URL)
    : (params.get("ws") || import.meta.env.VITE_REALTIME_WS_URL);
  if (explicitUrl) return withAnalysisId(explicitUrl, { preserveState });

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const configuredPath = interactionMode.value === "text"
    ? (params.get("textWsPath") || import.meta.env.VITE_TEXT_WS_PATH || "/ws/text")
    : (params.get("wsPath") || import.meta.env.VITE_REALTIME_WS_PATH || "/ws");
  const path = configuredPath.startsWith("/") ? configuredPath : `/${configuredPath}`;
  const url = new URL(`${protocol}://${window.location.host}${path}`);
  url.searchParams.set("analysis_id", getCurrentAnalysisId());
  if (preserveState) {
    url.searchParams.set("preserve_state", "1");
  }
  if (interactionMode.value === "voice") {
    url.searchParams.set("model", QWEN_REALTIME_MODEL);
  } else {
    url.searchParams.set("condition", "turn_based_text");
  }

  return url.toString();
}

function withAnalysisId(rawUrl, { preserveState = false } = {}) {
  const url = new URL(rawUrl, window.location.href);
  if (url.protocol === "http:") url.protocol = "ws:";
  if (url.protocol === "https:") url.protocol = "wss:";
  url.searchParams.set("analysis_id", getCurrentAnalysisId());
  if (preserveState) {
    url.searchParams.set("preserve_state", "1");
  }
  return url.toString();
}
</script>

<style scoped>
.dashboard {
  padding: 14px 16px 20px;
  max-width: 1600px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: #111827;
}

.dashboard__topbar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(280px, max-content) minmax(180px, 1fr);
  align-items: center;
  gap: 12px;
  min-height: 58px;
  margin-bottom: 10px;
  padding: 8px 16px;
  border: 1px solid #c9d3df;
  border-radius: 8px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.1);
  overflow-x: auto;
  overflow-y: visible;
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.brand-mark {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 3px;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2f7cff 0%, #145de4 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.32), 0 8px 18px rgba(37, 99, 235, 0.22);
}

.brand-mark span {
  width: 3px;
  border-radius: 999px;
  background: #dbeafe;
}

.brand-mark span:nth-child(1),
.brand-mark span:nth-child(5) { height: 9px; opacity: 0.78; }
.brand-mark span:nth-child(2),
.brand-mark span:nth-child(4) { height: 16px; }
.brand-mark span:nth-child(3) { height: 22px; }

.brand-copy {
  min-width: 0;
}

.dashboard__title {
  font-size: 20px;
  line-height: 1.05;
  font-weight: 700;
  margin: 0;
  letter-spacing: 0;
}

.brand-copy p {
  margin: 2px 0 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.15;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-status {
  display: flex;
  align-items: center;
  justify-self: center;
  gap: 6px;
  min-width: max-content;
  max-width: none;
  color: #1f2937;
  font-size: 14px;
  white-space: nowrap;
  overflow: visible;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #9ca3af;
  box-shadow: 0 0 0 2px rgba(156, 163, 175, 0.14);
}
.status-dot--connected {
  background: #25c63a;
  box-shadow: 0 0 0 2px rgba(37, 198, 58, 0.14);
}
.status-dot--connecting {
  background: #f5b51b;
  box-shadow: 0 0 0 2px rgba(245, 181, 27, 0.16);
}
.status-dot--disconnected { background: #9ca3af; }

.model-status__model {
  flex: 0 0 auto;
  overflow: visible;
  max-width: none;
  text-overflow: clip;
  font-weight: 650;
}

.model-status__state {
  flex: 0 0 auto;
  font-weight: 500;
}

.tool-call-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  min-width: max-content;
  max-width: none;
  overflow: visible;
  padding-left: 8px;
}

.tool-call-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: 0 0 auto;
  min-width: max-content;
  max-width: none;
  padding: 3px 7px;
  border: 1px solid #d8dee8;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  overflow: visible;
  text-overflow: clip;
  white-space: nowrap;
}

.tool-call-chip__icon {
  width: 13px;
  height: 13px;
  flex: 0 0 auto;
  fill: currentColor;
}

.interaction-control {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
}

.mode-switch {
  display: inline-grid;
  grid-template-columns: 1fr 1fr;
  flex: 0 0 auto;
  height: 34px;
  overflow: hidden;
  border: 1px solid #ccd6e3;
  border-radius: 8px;
  background: #ffffff;
}

.mode-switch__button {
  min-width: 54px;
  border: 0;
  border-right: 1px solid #dce4ef;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 12px;
  font-weight: 750;
  line-height: 1;
}

.mode-switch__button:last-child {
  border-right: 0;
}

.mode-switch__button:hover {
  background: #f1f6ff;
  color: #1d4ed8;
}

.mode-switch__button--active {
  background: #1d4ed8;
  color: #ffffff;
}

.mode-switch__button--active:hover {
  background: #1d4ed8;
  color: #ffffff;
}

.mic-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 132px;
  height: 40px;
  padding: 4px 12px 4px 5px;
  border: 1px solid #b8d3ff;
  border-radius: 999px;
  background: #eaf3ff;
  color: #225fcf;
  cursor: pointer;
  font-size: 14px;
  font-weight: 750;
  line-height: 1;
  white-space: nowrap;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.mic-pill:hover:not(:disabled) {
  background: #dcebff;
  border-color: #96bdff;
}

.mic-pill:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.mic-pill--recording {
  background: #dbeafe;
  border-color: #60a5fa;
  color: #1d4ed8;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.mic-pill__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.28);
}

.mic-pill__icon svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.2;
}

.mic-pill--recording .mic-pill__icon {
  background: #1d4ed8;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12), 0 6px 14px rgba(37, 99, 235, 0.28);
}

.text-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 126px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 750;
  line-height: 1;
  white-space: nowrap;
}

.text-status--busy {
  border-color: #f3c66d;
  background: #fff8e8;
  color: #92400e;
}

.status-filters {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  min-width: max-content;
  max-width: none;
  overflow: visible;
  white-space: nowrap;
}

.status-filters__label {
  flex: 0 0 auto;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}

.status-filter {
  flex: 0 0 auto;
  border: 1px solid #dbe4f0;
  background: #ffffff;
  color: #334155;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-family: monospace;
}

@media (max-width: 860px) {
  .dashboard {
    padding: 12px;
  }

  .dashboard__topbar {
    grid-template-columns: 1fr;
    gap: 8px;
    padding: 8px 10px;
  }

  .model-status {
    justify-self: start;
    flex-wrap: nowrap;
    white-space: nowrap;
  }

  .interaction-control {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .tool-call-strip,
  .status-filters {
    max-width: none;
    padding-left: 0;
  }
}

@media (max-width: 520px) {
  .brand-lockup {
    gap: 10px;
  }

  .brand-mark {
    width: 34px;
    height: 34px;
  }

  .dashboard__title {
    font-size: 20px;
  }

  .model-status {
    font-size: 13px;
  }

  .mic-pill {
    min-width: 0;
    height: 38px;
    font-size: 13px;
  }

  .mic-pill__icon {
    width: 28px;
    height: 28px;
  }
}

.dashboard__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
  gap: 16px;
}

.dashboard__transcript {
  margin-top: 18px;
  overflow: hidden;
  border: 1px solid #d7e1ee;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.transcript-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 44px;
  padding: 10px 16px;
  border-bottom: 1px solid #e1e8f2;
  background: #f8fbff;
}

.transcript-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  font-weight: 750;
  line-height: 1.2;
}

.transcript-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #475569;
  font-size: 13px;
  white-space: nowrap;
}

.transcript-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.transcript-toggle input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.transcript-toggle__track {
  position: relative;
  width: 34px;
  height: 18px;
  border-radius: 999px;
  background: #cbd5e1;
  transition: background 0.2s ease;
}

.transcript-toggle__track::after {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.24);
  content: "";
  transition: transform 0.2s ease;
}

.transcript-toggle input:checked + .transcript-toggle__track {
  background: #2563eb;
}

.transcript-toggle input:checked + .transcript-toggle__track::after {
  transform: translateX(16px);
}

.transcript-clear {
  border: 0;
  background: transparent;
  color: #1d4ed8;
  cursor: pointer;
  font-size: 13px;
  font-weight: 650;
  line-height: 1;
}

.transcript-clear:hover {
  color: #0f2f66;
}

.transcript-list {
  max-height: 230px;
  min-height: 26px;
  overflow-y: auto;
  background: #ffffff;
}

.transcript-exchange {
  padding: 3px 6px;
  border-bottom: 1px solid #edf2f7;
}

.transcript-exchange:last-child {
  border-bottom: 0;
}

.transcript-message {
  display: grid;
  grid-template-columns: 42px 28px minmax(0, 1fr) auto;
  align-items: start;
  column-gap: 6px;
  min-height: 18px;
  padding: 1px 4px;
  color: #1f2937;
  font-size: 12px;
  line-height: 1.35;
  cursor: pointer;
}

.transcript-message + .transcript-message {
  margin-top: 2px;
}

.transcript-message--interrupted {
  border-left: 2px solid #a8b0bc;
  color: rgba(31, 41, 55, 0.68);
}

.transcript-exchange--inline {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.transcript-exchange--inline .transcript-message {
  flex: 1 1 0;
  min-width: 0;
}

.transcript-exchange--inline .transcript-message--user {
  flex: 0 1 42%;
}

.transcript-exchange--inline .transcript-message + .transcript-message {
  margin-top: 0;
}

.transcript-time,
.transcript-role,
.transcript-content,
.transcript-meta {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.transcript-time {
  color: #64748b;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.transcript-role {
  color: #1d4ed8;
  font-size: 10px;
  font-weight: 750;
  line-height: 1.6;
}

.transcript-message--assistant .transcript-role {
  color: #0f2f66;
}

.transcript-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.transcript-text {
  min-width: 0;
  color: inherit;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.transcript-text--collapsed {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.transcript-message--user .transcript-text--collapsed {
  line-clamp: 1;
  -webkit-line-clamp: 1;
}

.transcript-message--assistant .transcript-text--collapsed {
  line-clamp: 2;
  -webkit-line-clamp: 2;
}

.transcript-meta {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  min-height: 16px;
}

.message-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border: 1px solid #c7ced8;
  border-radius: 50%;
  color: #64748b;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
}

.transcript-action-count {
  border: 1px solid #d8dee8;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  cursor: pointer;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  padding: 2px 6px;
  white-space: nowrap;
}

.transcript-tool-list {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.transcript-tool-item {
  max-width: 100%;
  overflow: hidden;
  border: 1px solid #dbe4f0;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10px;
  line-height: 1.2;
  padding: 2px 5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 700px) {
  .transcript-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .transcript-message {
    grid-template-columns: 38px 26px minmax(0, 1fr) auto;
  }

}

.dashboard {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  width: min(100vw, 3840px);
  max-width: 3840px;
  height: min(100dvh, 2160px);
  max-height: 2160px;
  overflow: hidden;
}

.dashboard__grid {
  min-height: 0;
  overflow: auto;
  align-content: start;
  padding-bottom: 4px;
}

.dashboard__transcript {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  height: clamp(320px, 34dvh, 560px);
  max-height: min(56dvh, 760px);
  min-height: 240px;
  resize: vertical;
  box-shadow: none;
}

.dashboard__text-entry {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  height: 300px;
  max-height: 300px;
  min-height: 300px;
  overflow: hidden;
  border: 1px solid #d7e1ee;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: none;
}

.transcript-header {
  min-height: 30px;
  padding: 5px 10px;
}

.transcript-header h3,
.transcript-actions,
.transcript-clear {
  font-size: 12px;
}

.transcript-toggle {
  display: none;
}

.transcript-list {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none;
  overflow: auto;
}

.text-history {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 8px 10px;
  border-bottom: 1px solid #e1e8f2;
  background: #ffffff;
  font-size: 12px;
  scrollbar-color: #cbd5e1 #f8fbff;
}

.text-history__exchange {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
  border-bottom: 1px solid #edf2f7;
}

.text-history__exchange:last-child {
  border-bottom: 0;
}

.text-history__message {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  align-items: start;
  gap: 6px;
  min-height: 18px;
  color: #1f2937;
  line-height: 1.35;
}

.text-history__message--user .text-history__role {
  color: #1d4ed8;
}

.text-history__message--assistant .text-history__role {
  color: #0f2f66;
}

.text-history__role {
  color: #0f2f66;
  font-size: 10px;
  font-weight: 750;
  line-height: 1.6;
}

.text-history__content {
  min-width: 0;
  overflow-wrap: anywhere;
}

.text-history__tools {
  grid-column: 2 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.text-pending {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  align-items: start;
  gap: 6px;
  flex: 0 0 auto;
  max-height: 58px;
  overflow: auto;
  padding: 5px 10px;
  border-bottom: 1px solid #e1e8f2;
  background: #eef6ff;
  color: #1f2937;
  font-size: 12px;
  line-height: 1.3;
}

.text-pending__role {
  color: #1d4ed8;
  font-size: 10px;
  font-weight: 800;
  line-height: 1.5;
}

.text-pending__content {
  min-width: 0;
  overflow-wrap: anywhere;
}

.text-composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  height: 35px;
  flex: 0 0 auto;
  padding: 4px 8px;
  background: #f8fbff;
}

.text-composer__input {
  width: 100%;
  min-height: 27px;
  max-height: 27px;
  resize: none;
  border: 1px solid #cbd7e6;
  border-radius: 8px;
  background: #ffffff;
  color: #111827;
  font: inherit;
  font-size: 13px;
  line-height: 1.2;
  outline: none;
  padding: 4px 8px;
}

.text-composer__input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.text-composer__send {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 82px;
  height: 27px;
  border: 1px solid #1d4ed8;
  border-radius: 8px;
  background: #2563eb;
  color: #ffffff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  line-height: 1;
}

.text-composer__send:hover:not(:disabled) {
  background: #1d4ed8;
}

.text-composer__send:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.text-composer__send svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.3;
}

.transcript-exchange {
  padding: 3px 6px;
}

.transcript-message {
  grid-template-columns: 42px 28px minmax(0, 1fr) auto;
  padding: 1px 4px;
  font-size: 12px;
}

.transcript-time {
  justify-self: start;
}

@media (max-width: 700px) {
  .dashboard {
    grid-template-rows: auto minmax(0, 1fr) auto;
  }

  .transcript-header {
    align-items: center;
    flex-direction: row;
  }

  .transcript-exchange--inline {
    display: block;
  }

  .transcript-exchange--inline .transcript-message + .transcript-message {
    margin-top: 2px;
  }

  .transcript-message {
    grid-template-columns: 38px 26px minmax(0, 1fr) auto;
  }

}
</style>
