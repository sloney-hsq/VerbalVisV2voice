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

      <div class="voice-control">
        <button
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
      </div>
    </header>

    <section v-if="store.activeFilters.length" class="filter-row" aria-label="Active filters">
      <span class="filter-row__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path d="M4 6h16l-6 7v4l-4 2v-6L4 6Z" />
        </svg>
      </span>
      <div class="filter-badges">
        <span class="filter-badge" v-for="(f, i) in store.activeFilters" :key="i">
          {{ filterLabel(f) }}
        </span>
      </div>
    </section>

    <!-- Chart Grid -->
    <section class="dashboard__grid">
      <ChartSlot v-for="view in store.views" :key="view.id" :view="view" />
    </section>

    <section v-if="transcriptRows.length" class="dashboard__transcript" aria-label="Session transcript">
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
          v-for="row in transcriptRows"
          :key="row.id"
          class="transcript-row"
          :class="[`transcript-row--${row.role}`, { 'transcript-row--live': row.live }]"
        >
          <span class="transcript-avatar" aria-hidden="true">
            <svg v-if="row.role === 'assistant'" viewBox="0 0 24 24">
              <path d="M9 4h6v3h2a3 3 0 0 1 3 3v5a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4v-5a3 3 0 0 1 3-3h2V4Z" />
              <path d="M9 13h.01M15 13h.01M10 17h4" />
            </svg>
            <svg v-else viewBox="0 0 24 24">
              <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
              <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
            </svg>
          </span>
          <span class="transcript-speaker">{{ speakerLabel(row) }}</span>
          <span class="transcript-text">{{ row.text }}</span>
          <span class="transcript-side">
            <span v-if="row.live" class="transcript-live">live transcribing...</span>
            <span v-if="store.sessionMode === 'barge_in' && row.live" class="transcript-mode">
              (barge-in)
            </span>
            <span class="transcript-time">{{ formatTranscriptTime(row.ts) }}</span>
          </span>
        </div>
      </div>
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
const isStartingListening = ref(false);
const autoScrollTranscripts = ref(true);
const transcriptList = ref(null);

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

const transcriptRows = computed(() => {
  const rows = store.transcripts.map((item, index) => ({
    ...item,
    id: `${item.ts || index}-${index}`,
    live: false,
  }));

  if (audio.isRecording.value || isStartingListening.value) {
    rows.push({
      id: "live-input",
      role: "user",
      text: audio.isRecording.value ? "Listening for your command." : "Starting microphone.",
      ts: Date.now(),
      live: true,
    });
  }

  return rows;
});

watch(
  () => [store.transcripts.length, audio.isRecording.value, isStartingListening.value],
  () => {
    if (!autoScrollTranscripts.value) return;
    nextTick(() => {
      if (transcriptList.value) {
        transcriptList.value.scrollTop = transcriptList.value.scrollHeight;
      }
    });
  }
);

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
  if (isStartingListening.value || audio.isRecording.value || recordButtonDisabled.value) {
    return;
  }

  isStartingListening.value = true;
  await ensureSessionReady({ fresh: true });
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

function speakerLabel(row) {
  return row.role === "assistant" ? "VerbalVis" : "You";
}

function formatTranscriptTime(ts) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(ts || Date.now()));
}

function filterLabel(filter) {
  return `${fieldLabel(filter.field)} ${operatorLabel(filter.operator)} ${formatValue(filter.value)}`;
}

function fieldLabel(field) {
  const labels = {
    order_month: "月份",
    order_week: "周",
    order_date: "日期",
    order_dow: "星期",
    order_hour: "小时",
    review_score: "评分",
    review_bucket: "评分分组",
    default_is_low_score: "默认低分",
    is_high_score: "高评分",
    customer_state: "州",
    product_category: "品类",
    delivery_days: "配送天数",
    estimated_delivery_days: "预计配送天数",
    delivery_delay_days: "延迟天数",
    delivery_speed_bucket: "配送速度",
    is_late: "是否延迟",
    delivery_status_bucket: "配送状态",
    delay_bucket: "延迟程度",
    revenue: "营收",
    order_item_revenue: "商品收入",
    revenue_bucket: "营收分组",
    item_count: "商品件数",
    product_count: "商品种数",
    category_count: "品类数",
    seller_count: "卖家数",
    freight_total: "运费",
    avg_item_price: "平均商品价格",
    freight_ratio: "运费占比",
    freight_bucket: "运费分组",
    order_size_bucket: "订单规模",
    primary_payment_type: "支付方式",
    payment_method_count: "支付方式数",
    max_payment_installments: "最大分期数",
    primary_payment_installments: "主要支付分期数",
    order_count: "订单量",
    low_score_ratio: "低分占比",
    late_ratio: "延迟率",
    on_time_ratio: "准时率",
    high_score_ratio: "高评分占比",
    avg_freight_ratio: "平均运费占比",
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
  gap: 18px;
  min-height: 78px;
  margin-bottom: 14px;
  padding: 13px 24px;
  border: 1px solid #c9d3df;
  border-radius: 8px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.1);
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.brand-mark {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 3px;
  width: 48px;
  height: 48px;
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
.brand-mark span:nth-child(5) { height: 13px; opacity: 0.78; }
.brand-mark span:nth-child(2),
.brand-mark span:nth-child(4) { height: 22px; }
.brand-mark span:nth-child(3) { height: 30px; }

.brand-copy {
  min-width: 0;
}

.dashboard__title {
  font-size: 23px;
  line-height: 1.08;
  font-weight: 700;
  margin: 0;
  letter-spacing: 0;
}

.brand-copy p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-status {
  display: flex;
  align-items: center;
  justify-self: center;
  gap: 7px;
  min-width: 0;
  max-width: 100%;
  color: #1f2937;
  font-size: 16px;
  white-space: nowrap;
}

.status-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #9ca3af;
  box-shadow: 0 0 0 3px rgba(156, 163, 175, 0.14);
}
.status-dot--connected {
  background: #25c63a;
  box-shadow: 0 0 0 3px rgba(37, 198, 58, 0.14);
}
.status-dot--connecting {
  background: #f5b51b;
  box-shadow: 0 0 0 3px rgba(245, 181, 27, 0.16);
}
.status-dot--disconnected { background: #9ca3af; }

.model-status__model {
  overflow: hidden;
  max-width: 260px;
  text-overflow: ellipsis;
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
  min-width: 0;
  max-width: 350px;
  overflow: hidden;
  padding-left: 8px;
}

.tool-call-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  max-width: 150px;
  padding: 4px 8px;
  border: 1px solid #d8dee8;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tool-call-chip__icon {
  width: 13px;
  height: 13px;
  flex: 0 0 auto;
  fill: currentColor;
}

.voice-control {
  display: flex;
  justify-content: flex-end;
  min-width: 0;
}

.mic-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 150px;
  height: 48px;
  padding: 6px 15px 6px 7px;
  border: 1px solid #b8d3ff;
  border-radius: 999px;
  background: #eaf3ff;
  color: #225fcf;
  cursor: pointer;
  font-size: 15px;
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
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.28);
}

.mic-pill__icon svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.2;
}

.mic-pill--recording .mic-pill__icon {
  background: #1d4ed8;
  box-shadow: 0 0 0 6px rgba(37, 99, 235, 0.12), 0 6px 14px rgba(37, 99, 235, 0.28);
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: -2px 0 14px;
  min-width: 0;
}

.filter-row__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #475569;
}

.filter-row__icon svg {
  width: 14px;
  height: 14px;
  fill: currentColor;
}

.filter-badges {
  display: flex;
  gap: 6px;
  flex: 0 1 auto;
  min-width: 0;
  max-width: 100%;
  overflow-x: auto;
  white-space: nowrap;
}
.filter-badge {
  flex: 0 0 auto;
  border: 1px solid #dbe4f0;
  background: #ffffff;
  color: #334155;
  padding: 4px 9px;
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
    gap: 12px;
    padding: 12px;
  }

  .model-status {
    justify-self: start;
    flex-wrap: wrap;
    white-space: normal;
  }

  .voice-control {
    justify-content: flex-start;
  }

  .tool-call-strip {
    max-width: 100%;
    padding-left: 0;
  }
}

@media (max-width: 520px) {
  .brand-lockup {
    gap: 10px;
  }

  .brand-mark {
    width: 44px;
    height: 44px;
  }

  .dashboard__title {
    font-size: 21px;
  }

  .model-status {
    font-size: 14px;
  }

  .mic-pill {
    min-width: 0;
    height: 44px;
    font-size: 14px;
  }

  .mic-pill__icon {
    width: 32px;
    height: 32px;
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
  overflow-y: auto;
  background: #ffffff;
}

.transcript-row {
  display: grid;
  grid-template-columns: 34px 78px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  padding: 10px 16px;
  border-bottom: 1px solid #edf2f7;
  color: #1f2937;
  font-size: 14px;
}

.transcript-row:last-child {
  border-bottom: 0;
}

.transcript-row--assistant {
  background: #fbfdff;
}

.transcript-row--live {
  background: #eff6ff;
}

.transcript-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.22);
}

.transcript-row--assistant .transcript-avatar {
  background: #0f2f66;
}

.transcript-row--live .transcript-avatar {
  background: #3b82f6;
}

.transcript-avatar svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.transcript-avatar svg path:first-child {
  fill: currentColor;
  stroke: none;
  opacity: 0.16;
}

.transcript-speaker {
  color: #1d4ed8;
  font-weight: 750;
}

.transcript-row--assistant .transcript-speaker {
  color: #0f2f66;
}

.transcript-text {
  min-width: 0;
  color: #1f2937;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.transcript-side {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-width: 0;
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.transcript-live,
.transcript-mode {
  color: #2563eb;
  font-weight: 750;
}

.transcript-live {
  font-style: italic;
}

.transcript-time {
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 700px) {
  .transcript-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .transcript-row {
    grid-template-columns: 32px minmax(0, 1fr);
    gap: 8px 10px;
  }

  .transcript-speaker {
    align-self: center;
  }

  .transcript-text,
  .transcript-side {
    grid-column: 2;
  }

  .transcript-side {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
