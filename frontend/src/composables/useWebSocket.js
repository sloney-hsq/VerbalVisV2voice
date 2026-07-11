import { onBeforeUnmount, ref } from "vue";
import { storeToRefs } from "pinia";
import { useDashboardStore } from "../stores/dashboard";
import { useRuntimeStore } from "../stores/runtime";

const ANALYSIS_ID_STORAGE_KEY = "verbalvis.analysisId";
const REALTIME_MODEL = "qwen3.5-omni-plus-realtime";

/**
 * One browser WebSocket for FD-Voice.
 *
 * The backend is the authority for turn detection and tool execution. The
 * frontend only routes audio, transcript, dashboard, and lifecycle events.
 */
export function useWebSocket(audioPlayer) {
  const dashboard = useDashboardStore();
  const runtime = useRuntimeStore();
  const { toolRunning } = storeToRefs(runtime);
  const socket = ref(null);

  let activeResponseId = null;
  let analysisId = getOrCreateAnalysisId();

  audioPlayer?.setPlaybackIdleHandler?.((event = {}) => {
    dashboard.isAssistantSpeaking = false;
    if (!toolRunning.value) runtime.setPhase("ready");
    sendPlaybackStopped(
      event.responseId || event.response_id || null,
      event.reason || "natural_end",
      event.playbackCursor || event.playback_cursor || null,
    );
  });

  function connect() {
    if (
      socket.value &&
      [WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.value.readyState)
    ) return;

    runtime.resetRuntime();
    runtime.setPhase("connecting");
    dashboard.connectionStatus = "connecting";
    dashboard.sessionReady = false;

    const ws = new WebSocket(buildWebSocketUrl());
    socket.value = ws;

    ws.onopen = () => {
      if (socket.value !== ws) return;
      dashboard.connectionStatus = "connected";
      runtime.setPhase("connecting");
    };

    ws.onclose = () => {
      if (socket.value !== ws) return;
      audioPlayer?.setCaptureBlocked?.(false);
      audioPlayer?.stopAssistantAudio?.({ blockNewAudio: true, reason: "socket_closed" });
      activeResponseId = null;
      dashboard.isAssistantSpeaking = false;
      dashboard.connectionStatus = "disconnected";
      dashboard.sessionReady = false;
      runtime.setPhase("disconnected", { toolRunning: false, tools: [] });
      socket.value = null;
    };

    ws.onerror = () => {
      if (socket.value !== ws) return;
      dashboard.connectionStatus = "disconnected";
      dashboard.sessionReady = false;
      runtime.setPhase("error", { toolRunning: false, tools: [] });
    };

    ws.onmessage = (event) => {
      try {
        dispatch(JSON.parse(event.data));
      } catch (error) {
        console.error("Invalid realtime message", error);
      }
    };
  }

  function dispatch(message = {}) {
    switch (message.type) {
      case "init":
        activeResponseId = null;
        dashboard.initViews(message.views || []);
        syncSessionInfo(message);
        runtime.updateDashboardState({
          ...runtime.dashboardState,
          views: message.views || [],
        });
        break;

      case "session_updated":
        syncSessionInfo(message);
        analysisId = normalizeAnalysisId(message.analysis_id) || analysisId;
        persistAnalysisId(analysisId);
        break;

      case "session_ready":
        dashboard.sessionReady = true;
        runtime.setPhase("ready");
        break;

      case "assistant_response_started":
        if (!message.response_id) break;
        activeResponseId = message.response_id;
        dashboard.beginAssistantResponse(activeResponseId);
        audioPlayer?.beginAssistantResponse?.(activeResponseId);
        runtime.setPhase("processing");
        break;

      case "audio":
        if (!message.response_id || message.response_id !== activeResponseId) break;
        if (audioPlayer?.enqueue?.(message.data, message) !== false) {
          dashboard.isAssistantSpeaking = true;
          runtime.setPhase("assistant_speaking");
        }
        break;

      case "transcript":
        handleTranscript(message);
        break;

      case "response_done":
        if (!message.response_id || message.response_id !== activeResponseId) break;
        dashboard.completeAssistantResponse(message.response_id);
        audioPlayer?.flush?.(message);
        activeResponseId = null;
        if (!toolRunning.value && !dashboard.isAssistantSpeaking) runtime.setPhase("ready");
        break;

      case "speech_started":
        runtime.setPhase("listening");
        dashboard.beginUserTranscript({
          utteranceId: message.utterance_id,
          text: message.text || "",
        });
        break;

      case "speech_stopped":
        if (!toolRunning.value) runtime.setPhase("processing");
        break;

      case "assistant_playback_stop":
      case "assistant_response_interrupted":
        stopAssistantPlayback(
          message.response_id,
          message.reason || "user_interruption",
        );
        break;

      case "tool_execution_started":
        audioPlayer?.setCaptureBlocked?.(true);
        runtime.startToolBatch(message);
        break;

      case "tool_execution_finished":
        audioPlayer?.setCaptureBlocked?.(false);
        runtime.finishToolBatch(message);
        break;

      case "tool_call":
        dashboard.addToolItem({
          name: message.name,
          arguments: message.arguments,
          summary: message.contract?.label,
          callId: message.call_id,
          responseId: message.response_id,
        });
        break;

      case "tool_result":
        dashboard.handleToolResult(message);
        runtime.recordToolResult(message);
        break;

      case "views_update":
        dashboard.updateViews(message.views || []);
        runtime.updateDashboardState({
          ...runtime.dashboardState,
          views: message.views || [],
        });
        break;

      case "dashboard_state":
        syncDashboardState(message.state || {});
        break;

      case "runtime_state":
        runtime.setPhase(message.phase || "ready", {
          toolRunning: Boolean(message.tool_running),
          tools: message.tools || [],
        });
        break;

      case "error":
        audioPlayer?.setCaptureBlocked?.(false);
        runtime.setPhase("error", { toolRunning: false, tools: [] });
        runtime.recordToolResult({
          success: false,
          error: message.message || "Realtime server error",
        });
        console.error("Realtime server error", message.message);
        break;
    }
  }

  function handleTranscript(message) {
    if (message.role === "assistant") {
      if (!message.response_id || message.response_id !== activeResponseId) return;
      dashboard.appendAssistantTranscript(message.response_id, message.delta || message.text || "");
      return;
    }
    if (message.role !== "user") return;

    const utteranceId = message.utterance_id || message.item_id || null;
    const hasDelta = typeof message.delta === "string";
    const text = hasDelta ? message.delta : message.text;
    const partial = (
      message.status === "partial" ||
      message.completed === false ||
      message.is_final === false ||
      hasDelta
    );
    if (partial) {
      dashboard.updateUserTranscript({ utteranceId, text, status: "listening" });
    } else {
      dashboard.completeUserTranscript(text, { utteranceId });
    }
  }

  function stopAssistantPlayback(responseId, reason) {
    const stoppedId = responseId || activeResponseId;
    dashboard.isAssistantSpeaking = false;
    dashboard.interruptAssistantResponse(stoppedId);

    const playbackCursor = audioPlayer?.stopAssistantAudio?.({
      responseId: stoppedId,
      blockNewAudio: true,
      reason,
    }) || null;

    if (!responseId || responseId === activeResponseId) activeResponseId = null;
    sendPlaybackStopped(stoppedId, reason, playbackCursor);
  }

  function syncDashboardState(state = {}) {
    runtime.updateDashboardState(state);
    if (Array.isArray(state.filters)) dashboard.activeFilters = state.filters;
    if (Array.isArray(state.highlighted)) {
      if (state.highlighted.length) {
        dashboard.highlightViews(
          state.highlighted,
          state.highlight_element ?? null,
          state.dim_others ?? true,
        );
      } else {
        dashboard.clearHighlight();
      }
    }
  }

  function syncSessionInfo(message = {}) {
    dashboard.setSessionInfo({
      mode: message.mode,
      inputMode: message.input_mode,
      turnDetection: message.turn_detection,
      provider: message.provider,
      model: message.model,
      inputAudioRate: message.input_audio_rate,
      outputAudioRate: message.output_audio_rate,
    });
  }

  function sendAudio(base64Pcm) {
    if (toolRunning.value) return false;
    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) return false;
    socket.value.send(JSON.stringify({ type: "audio", data: base64Pcm }));
    return true;
  }

  function sendPlaybackStopped(responseId, reason, playbackCursor) {
    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) return;
    socket.value.send(JSON.stringify({
      type: "playback_stopped",
      response_id: responseId,
      reason,
      playback_cursor: playbackCursor || null,
    }));
  }

  function disconnect() {
    audioPlayer?.setCaptureBlocked?.(false);
    audioPlayer?.stopAssistantAudio?.({ blockNewAudio: true, reason: "disconnect" });
    activeResponseId = null;
    dashboard.sessionReady = false;
    socket.value?.close();
    socket.value = null;
    runtime.setPhase("disconnected", { toolRunning: false, tools: [] });
  }

  function buildWebSocketUrl() {
    const params = new URLSearchParams(window.location.search);
    const explicit = params.get("ws") || import.meta.env.VITE_REALTIME_WS_URL;
    if (explicit) {
      const url = new URL(explicit, window.location.href);
      if (url.protocol === "http:") url.protocol = "ws:";
      if (url.protocol === "https:") url.protocol = "wss:";
      url.searchParams.set("analysis_id", analysisId);
      return url.toString();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const pathValue = params.get("wsPath") || import.meta.env.VITE_REALTIME_WS_PATH || "/ws";
    const path = pathValue.startsWith("/") ? pathValue : `/${pathValue}`;
    const url = new URL(`${protocol}//${window.location.host}${path}`);
    url.searchParams.set("analysis_id", analysisId);
    url.searchParams.set("model", REALTIME_MODEL);
    return url.toString();
  }

  function getOrCreateAnalysisId() {
    const params = new URLSearchParams(window.location.search);
    const forceNew = ["1", "true", "yes", "on"].includes(
      String(params.get("new_analysis") || params.get("newAnalysis") || "").toLowerCase(),
    );
    const explicit = normalizeAnalysisId(params.get("analysis_id") || params.get("analysisId"));
    let stored = "";
    if (!forceNew) {
      try {
        stored = normalizeAnalysisId(window.localStorage?.getItem(ANALYSIS_ID_STORAGE_KEY));
      } catch (_) {
        stored = "";
      }
    }
    const id = explicit || stored || `analysis-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 10)}`;
    return persistAnalysisId(id);
  }

  function persistAnalysisId(value) {
    const id = normalizeAnalysisId(value);
    window.__verbalvis_analysis_id = id;
    try {
      window.localStorage?.setItem(ANALYSIS_ID_STORAGE_KEY, id);
    } catch (_) {
      // Private browsing may disable storage; the in-memory id is sufficient.
    }
    return id;
  }

  function normalizeAnalysisId(value) {
    return String(value || "").trim().replace(/[^A-Za-z0-9_.-]/g, "-").slice(0, 80);
  }

  onBeforeUnmount(disconnect);

  return {
    socket,
    toolRunning,
    runtime,
    connect,
    sendAudio,
    sendPlaybackStopped,
    disconnect,
  };
}
