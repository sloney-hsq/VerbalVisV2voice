import { ref } from "vue";
import { defineStore } from "pinia";

const MAX_TRANSCRIPT_ITEMS = 120;

export const useDashboardStore = defineStore("dashboard", () => {
  const views = ref([]);
  const activeFilters = ref([]);
  const highlightedViewIds = ref([]);
  const highlightElement = ref(null);
  const highlightDimOthers = ref(true);

  // Flat chronological timeline: user, assistant, and tool items.
  const transcriptItems = ref([]);
  const currentUserItemId = ref(null);
  const currentAssistantResponseId = ref(null);

  const isAssistantSpeaking = ref(false);
  const connectionStatus = ref("disconnected");
  const sessionReady = ref(false);
  const sessionMode = ref("fd_voice");
  const inputMode = ref("semantic_vad");
  const turnDetection = ref("semantic_vad");
  const provider = ref("qwen");
  const model = ref("qwen3.5-omni-plus-realtime");
  const inputAudioRate = ref(16000);
  const outputAudioRate = ref(24000);

  // ------------------------------------------------------------------
  // Dashboard state
  // ------------------------------------------------------------------

  function initViews(viewList = []) {
    activeFilters.value = [];
    highlightedViewIds.value = [];
    highlightElement.value = null;
    highlightDimOthers.value = true;
    transcriptItems.value = [];
    currentUserItemId.value = null;
    currentAssistantResponseId.value = null;
    isAssistantSpeaking.value = false;
    applyAuthoritativeViews(viewList);
  }

  function updateViews(viewList = []) {
    applyAuthoritativeViews(viewList);
  }

  function applyAuthoritativeViews(viewList) {
    highlightedViewIds.value = viewList
      .filter((view) => Boolean(view.highlighted))
      .map((view) => view.id);
    if (!highlightedViewIds.value.length) {
      highlightElement.value = null;
    }
    views.value = viewList.map((view) => ({ ...view }));
  }

  function setSessionInfo(info = {}) {
    if (info.mode) sessionMode.value = info.mode;
    if (info.inputMode) inputMode.value = info.inputMode;
    if (info.turnDetection) turnDetection.value = info.turnDetection;
    if (info.provider) provider.value = info.provider;
    if (info.model) model.value = info.model;
    if (info.inputAudioRate) inputAudioRate.value = info.inputAudioRate;
    if (info.outputAudioRate) outputAudioRate.value = info.outputAudioRate;
  }

  function highlightViews(ids, element = null, dimOthers = true) {
    const normalized = uniqueIds(ids);
    highlightedViewIds.value = normalized;
    highlightElement.value = element;
    highlightDimOthers.value = Boolean(dimOthers);
    const selected = new Set(normalized);
    views.value.forEach((view) => {
      view.highlighted = selected.has(view.id);
    });
  }

  function clearHighlight() {
    highlightedViewIds.value = [];
    highlightElement.value = null;
    highlightDimOthers.value = true;
    views.value.forEach((view) => {
      view.highlighted = false;
    });
  }

  function handleToolResult(message = {}) {
    const payload = message.payload || {};
    if (message.tool === "highlight_visual" && message.success) {
      if (payload.action === "clear") clearHighlight();
      else {
        highlightViews(
          payload.view_ids || payload.highlighted_views || [payload.view_id],
          payload.highlight_element,
          payload.dim_others ?? true,
        );
      }
    }
    if (message.success && Array.isArray(payload.active_filters)) {
      activeFilters.value = payload.active_filters;
    }
    completeToolItem(message.call_id, message);
  }

  // ------------------------------------------------------------------
  // Flat transcript timeline
  // ------------------------------------------------------------------

  function beginUserTranscript({ utteranceId = null, text = "" } = {}) {
    const existing = findPendingUser(utteranceId);
    if (existing) return existing;

    const item = makeItem({
      role: "user",
      text,
      status: "listening",
      utteranceId: utteranceId || makeId("utterance"),
    });
    transcriptItems.value.push(item);
    currentUserItemId.value = item.id;
    trimTimeline();
    return item;
  }

  function updateUserTranscript({ utteranceId = null, text = "", status = "listening" } = {}) {
    const item = findPendingUser(utteranceId) || beginUserTranscript({ utteranceId, text });
    item.text = String(text || "");
    item.status = status;
    return item;
  }

  function completeUserTranscript(text, { utteranceId = null } = {}) {
    const clean = String(text || "").trim();
    if (!clean) return null;

    const item = findPendingUser(utteranceId);
    if (item) {
      item.text = clean;
      item.status = "completed";
      item.completedAt = Date.now();
      currentUserItemId.value = null;
      return item;
    }

    const completed = makeItem({
      role: "user",
      text: clean,
      status: "completed",
      utteranceId: utteranceId || makeId("utterance"),
    });
    completed.completedAt = completed.startedAt;
    transcriptItems.value.push(completed);
    trimTimeline();
    return completed;
  }

  function beginAssistantResponse(responseId) {
    if (responseId) currentAssistantResponseId.value = responseId;
  }

  function appendAssistantTranscript(responseId, delta = "") {
    const id = responseId || currentAssistantResponseId.value || makeId("response");
    currentAssistantResponseId.value = id;
    let item = findAssistant(id);
    if (!item) {
      item = makeItem({
        role: "assistant",
        responseId: id,
        status: "streaming",
      });
      transcriptItems.value.push(item);
      trimTimeline();
    }
    item.text += String(delta || "");
    item.status = "streaming";
    return item;
  }

  function completeAssistantResponse(responseId) {
    const item = findAssistant(responseId);
    if (item) {
      if (!item.text.trim()) removeItem(item.id);
      else if (item.status !== "interrupted") {
        item.status = "completed";
        item.completedAt = Date.now();
      }
    }
    if (!responseId || currentAssistantResponseId.value === responseId) {
      currentAssistantResponseId.value = null;
    }
  }

  function interruptAssistantResponse(responseId) {
    const id = responseId || currentAssistantResponseId.value;
    const item = findAssistant(id);
    if (item) {
      if (!item.text.trim()) removeItem(item.id);
      else {
        item.status = "interrupted";
        item.completedAt = Date.now();
      }
    }
    if (!id || currentAssistantResponseId.value === id) {
      currentAssistantResponseId.value = null;
    }
  }

  function addToolItem({ name, arguments: rawArguments, summary, callId, responseId } = {}) {
    const parameters = parseArguments(rawArguments);
    const item = makeItem({
      role: "tool",
      status: "running",
      callId: callId || makeId("call"),
      responseId: responseId || null,
      toolName: name || "tool",
      parameters,
      summary: summary || summarizeTool(name, parameters),
    });
    transcriptItems.value.push(item);
    trimTimeline();
    return item;
  }

  function completeToolItem(callId, result = {}) {
    if (!callId) return;
    const item = transcriptItems.value.find(
      (entry) => entry.role === "tool" && entry.callId === callId,
    );
    if (!item) return;
    item.status = result.success === false ? "error" : "completed";
    item.completedAt = Date.now();
  }

  function toggleToolDetails(itemId) {
    const item = transcriptItems.value.find((entry) => entry.id === itemId);
    if (item?.role === "tool") item.expanded = !item.expanded;
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  function findPendingUser(utteranceId) {
    if (utteranceId) {
      const exact = transcriptItems.value.find(
        (item) => item.role === "user" && item.utteranceId === utteranceId && item.status !== "completed",
      );
      if (exact) return exact;
    }
    if (!currentUserItemId.value) return null;
    return transcriptItems.value.find((item) => item.id === currentUserItemId.value) || null;
  }

  function findAssistant(responseId) {
    if (!responseId) return null;
    return transcriptItems.value.find(
      (item) => item.role === "assistant" && item.responseId === responseId,
    ) || null;
  }

  function makeItem({
    role,
    text = "",
    status = "completed",
    responseId = null,
    utteranceId = null,
    callId = null,
    toolName = null,
    parameters = null,
    summary = null,
  }) {
    const startedAt = Date.now();
    return {
      id: makeId(role),
      role,
      text,
      status,
      responseId,
      utteranceId,
      callId,
      toolName,
      parameters,
      summary,
      expanded: false,
      startedAt,
      completedAt: status === "completed" ? startedAt : null,
    };
  }

  function parseArguments(value) {
    if (!value) return {};
    if (typeof value === "object") return value;
    try {
      return JSON.parse(value);
    } catch (_) {
      return { value: String(value) };
    }
  }

  function summarizeTool(name, parameters = {}) {
    const label = String(name || "tool").replace(/_/g, " ");
    const first = Object.entries(parameters)
      .filter(([, value]) => value !== null && value !== undefined && value !== "")
      .slice(0, 2)
      .map(([key, value]) => `${key}=${compactValue(value)}`);
    return first.length ? `${label} · ${first.join(" · ")}` : label;
  }

  function compactValue(value) {
    if (Array.isArray(value)) return value.slice(0, 4).join(",");
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function uniqueIds(value) {
    const source = Array.isArray(value) ? value : [value];
    return [...new Set(source.filter(Boolean))];
  }

  function removeItem(itemId) {
    const index = transcriptItems.value.findIndex((item) => item.id === itemId);
    if (index >= 0) transcriptItems.value.splice(index, 1);
  }

  function trimTimeline() {
    if (transcriptItems.value.length > MAX_TRANSCRIPT_ITEMS) {
      transcriptItems.value = transcriptItems.value.slice(-MAX_TRANSCRIPT_ITEMS);
    }
  }

  function makeId(prefix) {
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  return {
    views,
    activeFilters,
    highlightedViewIds,
    highlightElement,
    highlightDimOthers,
    transcriptItems,
    isAssistantSpeaking,
    connectionStatus,
    sessionReady,
    sessionMode,
    inputMode,
    turnDetection,
    provider,
    model,
    inputAudioRate,
    outputAudioRate,
    initViews,
    updateViews,
    setSessionInfo,
    highlightViews,
    clearHighlight,
    handleToolResult,
    beginUserTranscript,
    updateUserTranscript,
    completeUserTranscript,
    beginAssistantResponse,
    appendAssistantTranscript,
    completeAssistantResponse,
    interruptAssistantResponse,
    addToolItem,
    completeToolItem,
    toggleToolDetails,
  };
});
