import { defineStore } from "pinia";
import { ref, computed } from "vue";

const MAX_SESSION_SUMMARIES = 10;

export const useDashboardStore = defineStore("dashboard", () => {
  // ---- state ----
  const views = ref([]);
  const activeFilters = ref([]);
  const highlightedViewIds = ref([]);
  const highlightedViewId = computed(() => highlightedViewIds.value[0] || null);
  const highlightElement = ref(null);
  const transcripts = ref([]); // {role, text}
  const sessionSummaries = ref([]);
  const isAssistantSpeaking = ref(false);
  const connectionStatus = ref("disconnected"); // disconnected | connecting | connected
  const sessionReady = ref(false);
  const sessionMode = ref("barge_in"); // barge_in | turn_based
  const inputMode = ref("semantic_vad");
  const provider = ref("qwen");
  const model = ref("qwen3.5-omni-plus-realtime");
  const inputAudioRate = ref(16000);
  const outputAudioRate = ref(24000);
  const recentToolCalls = ref([]);

  // ---- getters ----
  const viewIds = computed(() => views.value.map((v) => v.id));

  // ---- actions ----

  function initViews(viewList) {
    highlightedViewIds.value = viewList.filter((v) => v.highlighted).map((v) => v.id);
    const highlightedIds = new Set(highlightedViewIds.value);
    views.value = viewList.map((v) => ({ ...v, highlighted: highlightedIds.has(v.id) }));
  }

  function setSessionInfo(info = {}) {
    if (info.mode) sessionMode.value = info.mode;
    if (info.inputMode) inputMode.value = info.inputMode;
    if (info.provider) provider.value = info.provider;
    if (info.model) model.value = info.model;
    if (info.inputAudioRate) inputAudioRate.value = info.inputAudioRate;
    if (info.outputAudioRate) outputAudioRate.value = info.outputAudioRate;
  }

  function updateViews(viewList) {
    // Full replace: removes deleted views, updates/append the rest.
    const incomingIds = new Set(viewList.map((v) => v.id));
    const incomingHighlightedIds = viewList.filter((v) => v.highlighted).map((v) => v.id);
    highlightedViewIds.value = incomingHighlightedIds.length
      ? incomingHighlightedIds
      : highlightedViewIds.value.filter((id) => incomingIds.has(id));
    if (!highlightedViewIds.value.length) {
      highlightElement.value = null;
    }
    const highlightedIds = new Set(highlightedViewIds.value);
    const updated = viewList.map((v) => ({
      ...v,
      highlighted: highlightedIds.has(v.id),
    }));
    views.value = updated;
  }

  function appendView(view) {
    views.value.push({ ...view, highlighted: false });
  }

  function highlightView(viewId, element = null, dimOthers = true) {
    highlightViews([viewId], element, dimOthers);
  }

  function highlightViews(viewIdsToHighlight, element = null, dimOthers = true) {
    const ids = normalizeViewIds(viewIdsToHighlight);
    highlightedViewIds.value = ids;
    highlightElement.value = element;
    const highlightedIds = new Set(ids);
    views.value.forEach((v) => {
      if (highlightedIds.has(v.id)) {
        v.highlighted = true;
      } else if (dimOthers) {
        v.highlighted = false;
      }
    });
  }

  function clearHighlight() {
    highlightedViewIds.value = [];
    highlightElement.value = null;
    views.value.forEach((v) => {
      v.highlighted = false;
    });
  }

  function handleToolResult(msg) {
    const tool = msg.tool;
    if (tool === "highlight_visual" && msg.success && msg.payload) {
      if (msg.payload.action === "clear") {
        clearHighlight();
      } else {
        highlightViews(
          msg.payload.view_ids || msg.payload.highlighted_views || [msg.payload.view_id],
          msg.payload.highlight_element,
          msg.payload.dim_others ?? true
        );
      }
    } else if ((tool === "filter_data" || tool === "remove_filter") && msg.success && msg.payload) {
      activeFilters.value = msg.payload.active_filters || [];
    }
    // append_visual data comes via views_update
  }

  function recordToolCall(call = {}) {
    const item = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: call.name || "tool",
      arguments: call.arguments || "",
      ts: Date.now(),
    };
    recentToolCalls.value = [item, ...recentToolCalls.value].slice(0, 3);
  }

  function addTranscript(role, text) {
    transcripts.value.push({ role, text, ts: Date.now() });
    // Keep last 50
    if (transcripts.value.length > 50) {
      transcripts.value = transcripts.value.slice(-50);
    }
  }

  function clearTranscripts() {
    transcripts.value = [];
  }

  function addSessionSummary(message = {}) {
    const source = message?.summary && typeof message.summary === "object"
      ? message.summary
      : message;

    if (!source || typeof source !== "object") return;

    const ts = parseTimestamp(
      source.ts ??
      source.timestamp ??
      source.created_at ??
      message.ts ??
      message.timestamp
    );
    const item = {
      ...source,
      id: source.id || source.summary_id || `${ts}-${Math.random().toString(16).slice(2)}`,
      ts,
    };
    delete item.type;

    sessionSummaries.value = [...sessionSummaries.value, item].slice(-MAX_SESSION_SUMMARIES);
  }

  function clearSessionSummaries() {
    sessionSummaries.value = [];
  }

  function parseTimestamp(value) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string") {
      const parsed = Date.parse(value);
      if (Number.isFinite(parsed)) return parsed;
    }
    return Date.now();
  }

  function normalizeViewIds(value) {
    const source = Array.isArray(value) ? value : [value];
    const seen = new Set();
    const ids = [];
    for (const item of source) {
      if (!item || seen.has(item)) continue;
      seen.add(item);
      ids.push(item);
    }
    return ids;
  }

  return {
    views,
    activeFilters,
    highlightedViewIds,
    highlightedViewId,
    highlightElement,
    transcripts,
    sessionSummaries,
    isAssistantSpeaking,
    connectionStatus,
    sessionReady,
    sessionMode,
    inputMode,
    provider,
    model,
    inputAudioRate,
    outputAudioRate,
    recentToolCalls,
    viewIds,
    initViews,
    setSessionInfo,
    updateViews,
    appendView,
    highlightView,
    highlightViews,
    clearHighlight,
    handleToolResult,
    recordToolCall,
    addTranscript,
    clearTranscripts,
    addSessionSummary,
    clearSessionSummaries,
  };
});
