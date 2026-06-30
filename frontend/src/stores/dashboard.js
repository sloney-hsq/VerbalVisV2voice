import { defineStore } from "pinia";
import { ref, computed } from "vue";

export const useDashboardStore = defineStore("dashboard", () => {
  // ---- state ----
  const views = ref([]);
  const activeFilters = ref([]);
  const highlightedViewId = ref(null);
  const highlightElement = ref(null);
  const transcripts = ref([]); // {role, text}
  const isAssistantSpeaking = ref(false);
  const connectionStatus = ref("disconnected"); // disconnected | connecting | connected
  const sessionReady = ref(false);
  const sessionMode = ref("barge_in"); // barge_in | turn_based
  const inputMode = ref("local_vad");
  const provider = ref("qwen");
  const model = ref("qwen3.5-omni-plus-realtime");
  const inputAudioRate = ref(16000);
  const outputAudioRate = ref(24000);

  // ---- getters ----
  const viewIds = computed(() => views.value.map((v) => v.id));

  // ---- actions ----

  function initViews(viewList) {
    views.value = viewList.map((v) => ({ ...v, highlighted: false }));
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
    // Clear highlight if the highlighted view was removed (e.g. delete_visual).
    if (highlightedViewId.value && !incomingIds.has(highlightedViewId.value)) {
      highlightedViewId.value = null;
      highlightElement.value = null;
    }
    const updated = viewList.map((v) => ({
      ...v,
      highlighted: v.id === highlightedViewId.value,
    }));
    views.value = updated;
  }

  function appendView(view) {
    views.value.push({ ...view, highlighted: false });
  }

  function highlightView(viewId, element = null, dimOthers = true) {
    highlightedViewId.value = viewId;
    highlightElement.value = element;
    views.value.forEach((v) => {
      if (v.id === viewId) {
        v.highlighted = true;
      } else if (dimOthers) {
        v.highlighted = false;
      }
    });
  }

  function handleToolResult(msg) {
    const tool = msg.tool;
    if (tool === "highlight_visual" && msg.success && msg.payload) {
      highlightView(
        msg.payload.view_id,
        msg.payload.highlight_element,
        msg.payload.dim_others ?? true
      );
    } else if ((tool === "filter_data" || tool === "remove_filter") && msg.success && msg.payload) {
      activeFilters.value = msg.payload.active_filters || [];
    }
    // append_visual data comes via views_update
  }

  function addTranscript(role, text) {
    transcripts.value.push({ role, text, ts: Date.now() });
    // Keep last 50
    if (transcripts.value.length > 50) {
      transcripts.value = transcripts.value.slice(-50);
    }
  }

  return {
    views,
    activeFilters,
    highlightedViewId,
    highlightElement,
    transcripts,
    isAssistantSpeaking,
    connectionStatus,
    sessionReady,
    sessionMode,
    inputMode,
    provider,
    model,
    inputAudioRate,
    outputAudioRate,
    viewIds,
    initViews,
    setSessionInfo,
    updateViews,
    appendView,
    highlightView,
    handleToolResult,
    addTranscript,
  };
});
