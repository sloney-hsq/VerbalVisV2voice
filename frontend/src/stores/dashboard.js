import { defineStore } from "pinia";
import { computed, ref } from "vue";

export const useDashboardStore = defineStore("dashboard", () => {
  // ---- state ----
  const views = ref([]);
  const activeFilters = ref([]);
  const highlightedViewIds = ref([]);
  const highlightedViewId = computed(() => highlightedViewIds.value[0] || null);
  const highlightElement = ref(null);
  const transcriptExchanges = ref([]);
  const transcripts = computed(() => (
    transcriptExchanges.value.flatMap((exchange) => (
      [exchange.user, exchange.assistant].filter(Boolean)
    ))
  ));
  const isAssistantSpeaking = ref(false);
  const connectionStatus = ref("disconnected"); // disconnected | connecting | connected
  const sessionReady = ref(false);
  const sessionMode = ref("barge_in"); // barge_in | turn_based
  const inputMode = ref("semantic_vad");
  const turnDetection = ref("semantic_vad");
  const provider = ref("qwen");
  const model = ref("qwen3.5-omni-plus-realtime");
  const inputAudioRate = ref(16000);
  const outputAudioRate = ref(24000);
  const isTextTurnProcessing = ref(false);
  const recentToolCalls = ref([]);
  const currentUserEntryId = ref(null);
  const currentAssistantResponseId = ref(null);
  const pendingToolActions = ref([]);

  // ---- getters ----
  const viewIds = computed(() => views.value.map((v) => v.id));

  // ---- actions ----

  function initViews(viewList) {
    activeFilters.value = [];
    highlightedViewIds.value = viewList.filter((v) => v.highlighted).map((v) => v.id);
    const highlightedIds = new Set(highlightedViewIds.value);
    views.value = viewList.map((v) => ({ ...v, highlighted: highlightedIds.has(v.id) }));
    highlightElement.value = null;
    recentToolCalls.value = [];
    isTextTurnProcessing.value = false;
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
    if (role === "assistant") {
      const responseId = makeTranscriptId("assistant-response");
      beginAssistantResponse(responseId);
      appendAssistantTranscript(responseId, text || "");
      completeAssistantResponse(responseId);
      return;
    }
    completeUserTranscript(text);
  }

  function beginUserTranscript(options = {}) {
    const existing = findPendingUserMessage(options.utteranceId);
    if (existing) return existing;

    const message = createTranscriptMessage({
      role: "user",
      text: options.text || "",
      status: "listening",
      utteranceId: options.utteranceId || makeTranscriptId("utterance"),
    });
    currentUserEntryId.value = message.id;
    transcriptExchanges.value.push({
      id: makeTranscriptId("exchange"),
      user: message,
    });
    trimTranscriptHistory();
    return message;
  }

  function updateUserTranscript(options = {}) {
    const message = findPendingUserMessage(options.utteranceId) || beginUserTranscript(options);
    message.text = String(options.text || "");
    message.status = options.status || "listening";
    return message;
  }

  function completeUserTranscript(text, options = {}) {
    const cleanText = String(text || "").trim();
    if (!cleanText) return null;

    const message = findPendingUserMessage(options.utteranceId);
    if (message) {
      message.text = cleanText;
      message.status = "completed";
      message.completedAt = Date.now();
      currentUserEntryId.value = null;
      return message;
    }

    const completed = createTranscriptMessage({
      role: "user",
      text: cleanText,
      status: "completed",
      utteranceId: options.utteranceId || makeTranscriptId("utterance"),
    });
    completed.completedAt = completed.startedAt;
    transcriptExchanges.value.push({
      id: makeTranscriptId("exchange"),
      user: completed,
    });
    trimTranscriptHistory();
    return completed;
  }

  function beginAssistantResponse(responseId) {
    if (!responseId) return;
    currentAssistantResponseId.value = responseId;
  }

  function appendAssistantTranscript(responseId, delta = "") {
    const targetResponseId = responseId || currentAssistantResponseId.value || makeTranscriptId("response");
    currentAssistantResponseId.value = targetResponseId;
    const message = getOrCreateAssistantMessage(targetResponseId);
    message.text += String(delta || "");
    message.status = "streaming";
    return message;
  }

  function completeAssistantResponse(responseId) {
    const message = findAssistantMessageByResponseId(responseId);
    if (message) {
      if (!message.text.trim() && !message.toolActions.length) {
        removeTranscriptMessage(message.id);
      } else if (message.status !== "interrupted") {
        message.status = "completed";
        message.completedAt = Date.now();
      }
    }
    if (!responseId || currentAssistantResponseId.value === responseId) {
      currentAssistantResponseId.value = null;
    }
  }

  function suppressAssistantResponse(responseId) {
    const message = findAssistantMessageByResponseId(responseId);
    if (message) {
      if (message.toolActions.length) {
        pendingToolActions.value = [...message.toolActions, ...pendingToolActions.value];
      }
      removeTranscriptMessage(message.id);
    }
  }

  function interruptAssistantResponse(responseId) {
    const message = findAssistantMessageByResponseId(responseId || currentAssistantResponseId.value);
    if (message) {
      if (!message.text.trim() && !message.toolActions.length) {
        removeTranscriptMessage(message.id);
      } else {
        message.status = "interrupted";
        message.completedAt = Date.now();
      }
    }
    if (!responseId || currentAssistantResponseId.value === responseId) {
      currentAssistantResponseId.value = null;
    }
  }

  function addToolActionToTranscript(call = {}, responseId = null) {
    const action = createToolAction(call);
    const message = findAssistantMessageByResponseId(responseId || currentAssistantResponseId.value);
    if (message && message.text.trim()) {
      message.toolActions.push(action);
      return;
    }
    pendingToolActions.value.push(action);
  }

  function toggleTranscriptMessage(messageId) {
    const message = findTranscriptMessage(messageId);
    if (message) {
      message.expanded = !message.expanded;
    }
  }

  function toggleTranscriptActions(messageId) {
    const message = findTranscriptMessage(messageId);
    if (message) {
      message.toolActionsExpanded = !message.toolActionsExpanded;
    }
  }

  function clearTranscripts() {
    transcriptExchanges.value = [];
    currentUserEntryId.value = null;
    currentAssistantResponseId.value = null;
    pendingToolActions.value = [];
  }

  function setTextTurnProcessing(value) {
    isTextTurnProcessing.value = Boolean(value);
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

  function createTranscriptMessage({
    role,
    text = "",
    status = "completed",
    responseId = null,
    utteranceId = null,
    toolActions = [],
  }) {
    const startedAt = Date.now();
    return {
      id: makeTranscriptId(role),
      role,
      text,
      responseId,
      utteranceId,
      status,
      startedAt,
      ts: startedAt,
      completedAt: status === "completed" ? startedAt : undefined,
      expanded: false,
      toolActions,
      toolActionsExpanded: false,
    };
  }

  function getOrCreateAssistantMessage(responseId) {
    const existing = findAssistantMessageByResponseId(responseId);
    if (existing) return existing;

    const message = createTranscriptMessage({
      role: "assistant",
      status: "streaming",
      responseId,
      toolActions: pendingToolActions.value,
    });
    pendingToolActions.value = [];

    const exchange = findLatestExchangeWithoutAssistant();
    if (exchange) {
      exchange.assistant = message;
    } else {
      transcriptExchanges.value.push({
        id: makeTranscriptId("exchange"),
        assistant: message,
      });
    }
    trimTranscriptHistory();
    return message;
  }

  function findLatestExchangeWithoutAssistant() {
    for (let i = transcriptExchanges.value.length - 1; i >= 0; i -= 1) {
      const exchange = transcriptExchanges.value[i];
      if (!exchange.assistant) return exchange;
    }
    return null;
  }

  function findPendingUserMessage(utteranceId = null) {
    if (utteranceId) {
      const match = transcripts.value.find((message) => (
        message.role === "user" &&
        message.utteranceId === utteranceId &&
        message.status !== "completed"
      ));
      if (match) return match;
    }
    if (!currentUserEntryId.value) return null;
    return findTranscriptMessage(currentUserEntryId.value);
  }

  function findAssistantMessageByResponseId(responseId) {
    if (!responseId) return null;
    return transcripts.value.find((message) => (
      message.role === "assistant" && message.responseId === responseId
    )) || null;
  }

  function findTranscriptMessage(messageId) {
    if (!messageId) return null;
    return transcripts.value.find((message) => message.id === messageId) || null;
  }

  function removeTranscriptMessage(messageId) {
    for (let i = transcriptExchanges.value.length - 1; i >= 0; i -= 1) {
      const exchange = transcriptExchanges.value[i];
      if (exchange.user?.id === messageId) {
        delete exchange.user;
      }
      if (exchange.assistant?.id === messageId) {
        delete exchange.assistant;
      }
      if (!exchange.user && !exchange.assistant) {
        transcriptExchanges.value.splice(i, 1);
      }
    }
  }

  function createToolAction(call = {}) {
    const args = parseToolArguments(call.arguments);
    const name = call.name || "tool";
    return {
      name,
      summary: call.summary || summarizeToolAction(name, args),
      success: call.success !== false,
    };
  }

  function parseToolArguments(value) {
    if (!value) return {};
    if (typeof value === "object") return value;
    try {
      return JSON.parse(value);
    } catch (_) {
      return { value };
    }
  }

  function summarizeToolAction(name, args = {}) {
    const label = String(name || "tool").replace(/_/g, " ");
    const parts = Object.entries(args)
      .filter(([, value]) => value !== undefined && value !== null && value !== "")
      .slice(0, 2)
      .map(([key, value]) => `${key}=${formatActionValue(value)}`);
    return parts.length ? `${label}(${parts.join(", ")})` : label;
  }

  function formatActionValue(value) {
    if (Array.isArray(value)) return value.join("|");
    if (typeof value === "object" && value !== null) return JSON.stringify(value);
    return String(value);
  }

  function trimTranscriptHistory() {
    if (transcriptExchanges.value.length > 50) {
      transcriptExchanges.value = transcriptExchanges.value.slice(-50);
    }
  }

  function makeTranscriptId(prefix) {
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  return {
    views,
    activeFilters,
    highlightedViewIds,
    highlightedViewId,
    highlightElement,
    transcriptExchanges,
    transcripts,
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
    isTextTurnProcessing,
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
    beginUserTranscript,
    updateUserTranscript,
    completeUserTranscript,
    beginAssistantResponse,
    appendAssistantTranscript,
    completeAssistantResponse,
    suppressAssistantResponse,
    interruptAssistantResponse,
    addToolActionToTranscript,
    toggleTranscriptMessage,
    toggleTranscriptActions,
    clearTranscripts,
    setTextTurnProcessing,
  };
});
