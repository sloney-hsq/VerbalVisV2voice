<template>
  <main class="dashboard">
    <header class="topbar">
      <div class="brand">
        <span class="brand__mark" aria-hidden="true">
          <i></i><i></i><i></i><i></i><i></i>
        </span>
        <div>
          <h1>VerbalVis</h1>
          <p>Full-Duplex Conversational Visual Analytics</p>
        </div>
      </div>

      <div class="session-state" :title="sessionTitle">
        <span class="status-dot" :class="statusDotClass"></span>
        <span class="session-state__phase">{{ phaseLabel }}</span>
        <span
          v-if="ws.runtime.lastToolError"
          class="runtime-error"
          :title="ws.runtime.lastToolError"
        >Tool failed</span>
        <span v-if="store.activeFilters.length" class="filter-count">
          {{ store.activeFilters.length }} filters
        </span>
        <span v-else class="scope-all">All data</span>
        <span v-if="ws.runtime.filteredRows !== null" class="filtered-rows">
          {{ formatCount(ws.runtime.filteredRows) }} orders
        </span>
        <div v-if="store.activeFilters.length" class="filter-strip">
          <span v-for="(filter, index) in store.activeFilters" :key="`${filter.field}-${index}`">
            {{ filterLabel(filter) }}
          </span>
        </div>
      </div>

      <button
        class="mic-button"
        :class="{ 'mic-button--active': audio.isRecording.value }"
        :disabled="micDisabled"
        type="button"
        @click="toggleMicrophone"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" />
          <path d="M18 11a6 6 0 0 1-12 0M12 17v4M9 21h6" />
        </svg>
        <span>{{ micLabel }}</span>
      </button>
    </header>

    <section class="chart-grid" aria-label="Analytical dashboard">
      <ChartSlot v-for="view in store.views" :key="view.id" :view="view" />
    </section>

    <section class="timeline" aria-label="Session transcript">
      <div class="timeline__header">
        <strong>Transcript</strong>
        <span>{{ store.transcriptItems.length }} events</span>
      </div>

      <div ref="timelineList" class="timeline__list" aria-live="polite">
        <div
          v-for="item in store.transcriptItems"
          :key="item.id"
          class="timeline-row"
          :class="[
            `timeline-row--${item.role}`,
            {
              'timeline-row--expanded': item.expanded,
              'timeline-row--error': item.status === 'error',
            },
          ]"
          @click="item.role === 'tool' && store.toggleToolDetails(item.id)"
        >
          <time>{{ formatTime(item.startedAt) }}</time>
          <span class="timeline-row__role">{{ roleLabel(item) }}</span>

          <div class="timeline-row__body">
            <template v-if="item.role === 'tool'">
              <div class="tool-summary" :title="item.summary">
                <span class="tool-caret">{{ item.expanded ? '▾' : '▸' }}</span>
                <span>{{ item.summary || formatToolName(item.toolName) }}</span>
              </div>
              <div v-if="item.expanded" class="tool-details" @click.stop>
                <div><b>Tool</b><code>{{ item.toolName }}</code></div>
                <div><b>Parameters</b><pre>{{ formatParameters(item.parameters) }}</pre></div>
                <div v-if="item.error" class="tool-error">
                  <b>Error</b><code>{{ item.error }}</code>
                </div>
              </div>
            </template>

            <template v-else>
              <span
                class="message-text"
                :title="item.text"
              >{{ item.text || statusPlaceholder(item) }}</span>
              <span
                v-if="item.role === 'assistant' && item.status === 'interrupted'"
                class="interrupted-mark"
                title="Assistant response interrupted"
              >×</span>
            </template>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import ChartSlot from "./ChartSlot.vue";
import { useAudio } from "../composables/useAudio";
import { useWebSocket } from "../composables/useWebSocket";
import { useDashboardStore } from "../stores/dashboard";

const store = useDashboardStore();
const audio = useAudio();
const ws = useWebSocket(audio);
const timelineList = ref(null);
const isStartingMic = ref(false);

const phaseLabel = computed(() => ws.runtime.phaseLabel);
const sessionTitle = computed(() => (
  `${store.model} · ${store.connectionStatus} · ${phaseLabel.value}`
));
const statusDotClass = computed(() => ({
  "status-dot--connected": store.connectionStatus === "connected",
  "status-dot--connecting": store.connectionStatus === "connecting",
  "status-dot--error": ws.runtime.phase === "error",
}));
const micDisabled = computed(() => (
  isStartingMic.value ||
  ws.toolRunning.value ||
  store.connectionStatus !== "connected" ||
  !store.sessionReady
));
const micLabel = computed(() => {
  if (ws.toolRunning.value) return "Updating dashboard";
  if (isStartingMic.value) return "Starting";
  if (store.isAssistantSpeaking) return "Assistant speaking";
  if (audio.isRecording.value) return "Listening";
  if (store.connectionStatus === "connecting") return "Connecting";
  if (!store.sessionReady) return "Offline";
  return "Start mic";
});
const timelineVersion = computed(() => (
  store.transcriptItems
    .map((item) => `${item.id}:${item.text?.length || 0}:${item.status}:${item.expanded}`)
    .join("|")
));

watch(timelineVersion, () => {
  nextTick(() => {
    if (timelineList.value) timelineList.value.scrollTop = timelineList.value.scrollHeight;
  });
});

onMounted(() => {
  ws.connect();
  window.addEventListener("keydown", handleShortcut);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleShortcut);
  audio.stopRecording();
  ws.disconnect();
});

async function startMicrophone() {
  if (micDisabled.value || audio.isRecording.value) return;
  isStartingMic.value = true;
  try {
    await audio.startRecording((base64Pcm) => ws.sendAudio(base64Pcm));
  } catch (error) {
    console.error("Unable to start microphone", error);
    audio.stopRecording();
  } finally {
    isStartingMic.value = false;
  }
}

function toggleMicrophone() {
  if (audio.isRecording.value) audio.stopRecording();
  else startMicrophone();
}

function handleShortcut(event) {
  if (event.code !== "Space" || event.repeat || shouldIgnoreShortcut(event.target)) return;
  event.preventDefault();
  toggleMicrophone();
}

function shouldIgnoreShortcut(target) {
  const tag = target?.tagName?.toLowerCase();
  return tag === "input" || tag === "textarea" || target?.isContentEditable;
}

function roleLabel(item) {
  if (item.role === "assistant") return "AI";
  if (item.role === "tool") return "TOOL";
  return "YOU";
}

function statusPlaceholder(item) {
  if (item.status === "listening") return "Listening…";
  if (item.status === "streaming") return "…";
  return "";
}

function formatTime(timestamp) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(timestamp || Date.now()));
}

function formatToolName(name) {
  return String(name || "tool").replace(/_/g, " ");
}

function formatParameters(parameters) {
  return JSON.stringify(parameters || {}, null, 2);
}

function formatCount(value) {
  return new Intl.NumberFormat().format(Number(value) || 0);
}

function filterLabel(filter) {
  const labels = {
    customer_state: "State",
    product_category: "Category",
    order_date: "Date",
    order_week: "Week",
    order_month: "Month",
    review_score: "Score",
    delivery_days: "Delivery days",
    is_late: "Late",
  };
  const operators = {
    eq: "=",
    neq: "≠",
    in: "in",
    gte: "≥",
    lte: "≤",
    between: "between",
  };
  const value = Array.isArray(filter.value) ? filter.value.join(" – ") : filter.value;
  return `${labels[filter.field] || filter.field} ${operators[filter.operator] || filter.operator} ${value}`;
}
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100dvh;
  min-height: 0;
  padding: 12px 14px;
  gap: 10px;
  overflow: hidden;
  color: #172033;
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.topbar {
  display: grid;
  grid-template-columns: minmax(220px, auto) minmax(0, 1fr) auto;
  align-items: center;
  min-height: 54px;
  padding: 7px 11px;
  gap: 12px;
  border: 1px solid #d9e1ec;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.brand {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 9px;
}

.brand__mark {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  border-radius: 9px;
  background: #2563eb;
}

.brand__mark i {
  width: 2px;
  border-radius: 999px;
  background: #dbeafe;
}
.brand__mark i:nth-child(1), .brand__mark i:nth-child(5) { height: 8px; }
.brand__mark i:nth-child(2), .brand__mark i:nth-child(4) { height: 14px; }
.brand__mark i:nth-child(3) { height: 21px; }

.brand h1 {
  margin: 0;
  font-size: 17px;
  line-height: 1.05;
}

.brand p {
  margin: 2px 0 0;
  color: #718096;
  font-size: 10px;
  line-height: 1.15;
  white-space: nowrap;
}

.session-state {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 7px;
  color: #475569;
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #94a3b8;
}
.status-dot--connected { background: #22c55e; }
.status-dot--connecting { background: #f59e0b; }
.status-dot--error { background: #ef4444; }

.session-state__phase,
.filter-count,
.scope-all,
.filtered-rows,
.runtime-error {
  flex: 0 0 auto;
  font-weight: 650;
}

.filter-count {
  padding-left: 7px;
  border-left: 1px solid #dbe3ef;
  color: #2563eb;
}

.scope-all,
.filtered-rows {
  color: #64748b;
}

.runtime-error {
  padding: 2px 7px;
  border: 1px solid #fecaca;
  border-radius: 999px;
  background: #fef2f2;
  color: #b91c1c;
}

.filter-strip {
  display: flex;
  min-width: 0;
  gap: 5px;
  overflow-x: auto;
  scrollbar-width: none;
}
.filter-strip::-webkit-scrollbar { display: none; }
.filter-strip span {
  flex: 0 0 auto;
  max-width: 220px;
  padding: 2px 7px;
  overflow: hidden;
  border: 1px solid #d8e5f8;
  border-radius: 999px;
  background: #f3f8ff;
  color: #315c9a;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mic-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 126px;
  height: 36px;
  padding: 0 12px;
  gap: 7px;
  border: 1px solid #bfd4f7;
  border-radius: 999px;
  background: #edf5ff;
  color: #1d5ec7;
  cursor: pointer;
  font-weight: 700;
}
.mic-button:disabled { cursor: not-allowed; opacity: 0.58; }
.mic-button--active { background: #dbeafe; border-color: #60a5fa; }
.mic-button svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 540px);
  grid-auto-flow: row;
  grid-auto-rows: auto;
  flex: 1 1 auto;
  min-height: 0;
  gap: 12px;
  overflow: auto;
  align-content: start;
  align-items: start;
  justify-content: center;
  padding: 1px 2px 6px;
}

.timeline {
  display: flex;
  flex: 0 0 250px;
  height: 250px;
  overflow: hidden;
  border: 1px solid #d9e1ec;
  border-radius: 12px;
  background: #fff;
}

.timeline__header {
  display: flex;
  flex: 0 0 82px;
  flex-direction: column;
  justify-content: center;
  padding: 8px 10px;
  border-right: 1px solid #e6ebf2;
  background: #f8fafc;
  font-size: 11px;
}
.timeline__header strong { font-size: 12px; }
.timeline__header span { margin-top: 3px; color: #94a3b8; }

.timeline__list {
  flex: 1 1 auto;
  min-width: 0;
  overflow-y: auto;
  padding: 4px 7px;
}

.timeline-row {
  display: grid;
  grid-template-columns: 58px 40px minmax(0, 1fr);
  min-height: 25px;
  align-items: start;
  border-bottom: 1px solid #f0f3f7;
  color: #334155;
  font-size: 11px;
  line-height: 1.35;
}
.timeline-row:last-child { border-bottom: 0; }
.timeline-row time {
  padding: 5px 4px 4px 0;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}
.timeline-row__role {
  padding: 5px 5px 4px 0;
  color: #64748b;
  font-size: 10px;
  font-weight: 800;
}
.timeline-row--user .timeline-row__role { color: #2563eb; }
.timeline-row--assistant .timeline-row__role { color: #7c3aed; }
.timeline-row--tool .timeline-row__role { color: #b45309; }
.timeline-row__body {
  display: flex;
  min-width: 0;
  padding: 4px 0;
  gap: 5px;
}

.message-text {
  display: -webkit-box;
  min-width: 0;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  white-space: normal;
  overflow-wrap: anywhere;
}

.interrupted-mark {
  flex: 0 0 auto;
  color: #dc2626;
  font-size: 13px;
  font-weight: 800;
}

.timeline-row--tool { cursor: pointer; }
.timeline-row--error .timeline-row__role,
.timeline-row--error .tool-summary { color: #b91c1c; }
.tool-summary {
  display: flex;
  min-width: 0;
  width: 100%;
  overflow: hidden;
  color: #92400e;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-summary span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
}
.tool-caret { flex: 0 0 14px; }

.timeline-row--expanded .timeline-row__body {
  display: block;
}
.tool-details {
  display: grid;
  grid-template-columns: minmax(160px, 0.35fr) minmax(260px, 1fr);
  margin: 3px 0 5px;
  padding: 7px 9px;
  gap: 10px;
  border: 1px solid #fde1b6;
  border-radius: 7px;
  background: #fffbeb;
  cursor: default;
}
.tool-details div { min-width: 0; }
.tool-details .tool-error {
  grid-column: 1 / -1;
  padding-top: 6px;
  border-top: 1px solid #fecaca;
}
.tool-details .tool-error b,
.tool-details .tool-error code { color: #b91c1c; }
.tool-details b {
  display: block;
  margin-bottom: 3px;
  color: #92400e;
  font-size: 9px;
  text-transform: uppercase;
}
.tool-details code,
.tool-details pre {
  display: block;
  margin: 0;
  overflow: auto;
  color: #3f3f46;
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: 10px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 899px) {
  .topbar { grid-template-columns: 1fr auto; }
  .session-state { grid-column: 1 / -1; grid-row: 2; }
  .brand p { display: none; }
  .chart-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
