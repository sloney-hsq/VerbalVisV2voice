import { computed, ref } from "vue";
import { defineStore } from "pinia";

export const useRuntimeStore = defineStore("runtime", () => {
  const phase = ref("connecting");
  const toolRunning = ref(false);
  const activeTools = ref([]);
  const dashboardState = ref({
    filters: [],
    highlighted: [],
    views: [],
    low_score_threshold: 2,
  });
  const filteredRows = ref(null);
  const lastToolSummary = ref("");
  const lastToolError = ref("");
  const lastToolDurationMs = ref(null);
  const ignoredAudioChunks = ref(0);

  const phaseLabel = computed(() => {
    switch (phase.value) {
      case "ready":
        return "Ready";
      case "listening":
        return "Listening";
      case "processing":
        return "Understanding request";
      case "assistant_speaking":
        return "Assistant speaking";
      case "reading_dashboard":
        return "Reading dashboard";
      case "updating_dashboard":
        return "Updating dashboard";
      case "error":
        return "Runtime error";
      case "disconnected":
        return "Disconnected";
      default:
        return "Connecting";
    }
  });

  const phaseDetail = computed(() => {
    if (toolRunning.value && activeTools.value.length) {
      return activeTools.value.map((tool) => tool.label || tool.name).join(" · ");
    }
    if (phase.value === "ready" && lastToolSummary.value) {
      return lastToolSummary.value;
    }
    return "";
  });

  const activeFilterCount = computed(() => (
    Array.isArray(dashboardState.value?.filters)
      ? dashboardState.value.filters.length
      : 0
  ));

  const viewCount = computed(() => (
    Array.isArray(dashboardState.value?.views)
      ? dashboardState.value.views.length
      : 0
  ));

  function setPhase(nextPhase, options = {}) {
    phase.value = nextPhase || "ready";
    if (Array.isArray(options.tools)) {
      activeTools.value = options.tools;
    } else if (["ready", "listening", "assistant_speaking", "disconnected", "error"].includes(phase.value)) {
      activeTools.value = [];
    }
    if (typeof options.toolRunning === "boolean") {
      toolRunning.value = options.toolRunning;
    }
  }

  function startToolBatch(message = {}) {
    toolRunning.value = true;
    activeTools.value = Array.isArray(message.tools) ? message.tools : [];
    phase.value = message.changes_dashboard ? "updating_dashboard" : "reading_dashboard";
    lastToolError.value = "";
    ignoredAudioChunks.value = 0;
  }

  function finishToolBatch(message = {}) {
    toolRunning.value = false;
    activeTools.value = [];
    phase.value = message.followup_requested === false ? "ready" : "processing";
    lastToolDurationMs.value = Number.isFinite(Number(message.duration_ms))
      ? Number(message.duration_ms)
      : null;
    ignoredAudioChunks.value = Number(message.ignored_audio_chunks || 0);
  }

  function recordToolResult(message = {}) {
    if (message.summary) lastToolSummary.value = String(message.summary);
    if (message.success === false) {
      lastToolError.value = String(message.error || message.summary || "Tool execution failed");
    } else {
      lastToolError.value = "";
    }

    const rows = message.payload?.filtered_rows;
    if (rows !== undefined && rows !== null && Number.isFinite(Number(rows))) {
      filteredRows.value = Number(rows);
    }
  }

  function updateDashboardState(state = {}) {
    dashboardState.value = {
      filters: Array.isArray(state.filters) ? state.filters : [],
      highlighted: Array.isArray(state.highlighted) ? state.highlighted : [],
      views: Array.isArray(state.views) ? state.views : [],
      low_score_threshold: Number(state.low_score_threshold || 2),
      ...state,
    };
  }

  function resetRuntime() {
    phase.value = "connecting";
    toolRunning.value = false;
    activeTools.value = [];
    dashboardState.value = {
      filters: [],
      highlighted: [],
      views: [],
      low_score_threshold: 2,
    };
    filteredRows.value = null;
    lastToolSummary.value = "";
    lastToolError.value = "";
    lastToolDurationMs.value = null;
    ignoredAudioChunks.value = 0;
  }

  return {
    phase,
    toolRunning,
    activeTools,
    dashboardState,
    filteredRows,
    lastToolSummary,
    lastToolError,
    lastToolDurationMs,
    ignoredAudioChunks,
    phaseLabel,
    phaseDetail,
    activeFilterCount,
    viewCount,
    setPhase,
    startToolBatch,
    finishToolBatch,
    recordToolResult,
    updateDashboardState,
    resetRuntime,
  };
});
