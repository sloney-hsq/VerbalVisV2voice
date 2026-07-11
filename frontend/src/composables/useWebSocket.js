import { ref, onBeforeUnmount } from "vue";
import { storeToRefs } from "pinia";
import { useDashboardStore } from "../stores/dashboard";
import { useRuntimeStore } from "../stores/runtime";

const ANALYSIS_ID_STORAGE_KEY = "verbalvis.analysisId";

/**
 * WebSocket composable for the VerbalVis backend.
 * Dispatches incoming messages to the dashboard/runtime stores and audio player.
 */
export function useWebSocket(audioPlayer) {
  const store = useDashboardStore();
  const runtime = useRuntimeStore();
  const { toolRunning } = storeToRefs(runtime);
  const socket = ref(null);

  let suppressCurrentAssistantTranscript = false;
  let activeResponseId = null;
  let manualClose = false;
  let lastUrl = null;
  let analysisId = getOrCreateAnalysisId();

  audioPlayer?.setPlaybackIdleHandler?.((event = {}) => {
    const responseId = event.responseId || event.response_id || null;
    store.isAssistantSpeaking = false;
    if (!toolRunning.value) runtime.setPhase("ready");
    sendPlaybackStopped(
      responseId,
      event.reason || "natural_end",
      event.playbackCursor || event.playback_cursor || null
    );
  });

  function connect(url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?model=qwen3.5-omni-plus-realtime`) {
    if (
      socket.value &&
      (socket.value.readyState === WebSocket.OPEN || socket.value.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    manualClose = false;
    lastUrl = url;
    runtime.resetRuntime();
    runtime.setPhase("connecting");
    store.connectionStatus = "connecting";
    store.sessionReady = false;
    const ws = new WebSocket(url);
    socket.value = ws;

    ws.onopen = () => {
      store.connectionStatus = "connected";
      runtime.setPhase("connecting");
      console.log("%c[WS] connected to backend", "color: #22c55e; font-weight: bold");
    };

    ws.onclose = () => {
      if (socket.value !== ws) return;
      store.connectionStatus = "disconnected";
      store.sessionReady = false;
      activeResponseId = null;
      runtime.setPhase("disconnected", { toolRunning: false, tools: [] });
      socket.value = null;
    };

    ws.onerror = (event) => {
      if (socket.value !== ws) return;
      console.warn("[WS] backend connection error", event);
      store.connectionStatus = "disconnected";
      store.sessionReady = false;
      activeResponseId = null;
      runtime.setPhase("error", { toolRunning: false, tools: [] });
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      _dispatch(msg);
    };
  }

  function _dispatch(msg) {
    switch (msg.type) {
      case "init":
        activeResponseId = null;
        runtime.setPhase("connecting", { toolRunning: false, tools: [] });
        _syncDashboardState({
          ...runtime.dashboardState,
          views: msg.views || [],
        });
        store.initViews(msg.views);
        store.setSessionInfo({
          mode: msg.mode,
          inputMode: msg.input_mode,
          turnDetection: msg.turn_detection,
          provider: msg.provider,
          model: msg.model,
          inputAudioRate: msg.input_audio_rate,
          outputAudioRate: msg.output_audio_rate,
        });
        break;

      case "assistant_response_started":
        if (!msg.response_id) break;
        activeResponseId = msg.response_id;
        suppressCurrentAssistantTranscript = false;
        runtime.setPhase("processing");
        store.beginAssistantResponse(msg.response_id);
        audioPlayer?.beginAssistantResponse?.(msg.response_id);
        break;

      case "views_update":
        store.updateViews(msg.views);
        runtime.updateDashboardState({
          ...runtime.dashboardState,
          views: msg.views || [],
        });
        break;

      case "dashboard_state":
        _syncDashboardState(msg.state || {});
        break;

      case "runtime_state":
        runtime.setPhase(msg.phase || "ready", {
          toolRunning: Boolean(msg.tool_running),
          tools: msg.tools || [],
        });
        break;

      case "audio":
        if (!msg.response_id || msg.response_id !== activeResponseId) {
          break;
        }
        runtime.setPhase("assistant_speaking");
        if (audioPlayer) {
          const didEnqueue = audioPlayer.enqueue(msg.data, {
            response_id: msg.response_id,
            item_id: msg.item_id,
            content_index: msg.content_index,
            sample_rate: msg.sample_rate,
          });
          if (didEnqueue !== false) {
            store.isAssistantSpeaking = true;
          }
        }
        break;

      case "transcript":
        if (msg.role === "assistant") {
          if (!msg.response_id || msg.response_id !== activeResponseId) {
            break;
          }
          if (!suppressCurrentAssistantTranscript) {
            store.appendAssistantTranscript(msg.response_id, msg.delta || "");
          }
        } else if (msg.role === "user") {
          _handleUserTranscript(msg);
        }
        break;

      case "suppress_assistant_buffer":
        suppressCurrentAssistantTranscript = true;
        store.suppressAssistantResponse(msg.response_id || activeResponseId);
        break;

      case "response_done":
        if (!msg.response_id || msg.response_id !== activeResponseId) {
          break;
        }
        store.completeAssistantResponse(msg.response_id);
        suppressCurrentAssistantTranscript = false;
        if (audioPlayer) {
          audioPlayer.flush({
            response_id: msg.response_id,
          });
        }
        activeResponseId = null;
        if (!toolRunning.value && !store.isAssistantSpeaking) {
          runtime.setPhase("ready");
        }
        break;

      case "assistant_response_done":
        if (msg.response_id && msg.response_id === activeResponseId) {
          store.completeAssistantResponse(msg.response_id);
          activeResponseId = null;
        }
        suppressCurrentAssistantTranscript = false;
        if (!toolRunning.value && !store.isAssistantSpeaking) {
          runtime.setPhase("ready");
        }
        break;

      case "speech_started":
        runtime.setPhase("listening");
        if (msg.text || msg.utterance_id) {
          store.beginUserTranscript({
            utteranceId: msg.utterance_id,
            text: msg.text || "",
          });
        }
        break;

      case "speech_stopped":
        if (!toolRunning.value) runtime.setPhase("processing");
        break;

      case "assistant_playback_stop":
        _stopAssistantPlayback(msg.response_id, msg.reason || "assistant_playback_stop");
        break;

      case "assistant_playback_invalidated":
        if (msg.response_id) {
          _stopAssistantPlayback(msg.response_id, msg.reason || "assistant_playback_invalidated");
        }
        break;

      case "assistant_response_interrupted":
        _stopAssistantPlayback(msg.response_id, msg.reason || "assistant_response_interrupted");
        break;

      case "tool_execution_started":
        runtime.startToolBatch(msg);
        console.log("%c[TOOLS] dashboard operation started", "color: #f59e0b; font-weight: bold");
        break;

      case "tool_execution_finished":
        runtime.finishToolBatch(msg);
        console.log("%c[TOOLS] dashboard operation finished", "color: #22c55e; font-weight: bold");
        break;

      case "tool_call":
        console.log(`%c>>> TOOL CALL: ${msg.name}(${msg.arguments})`, "color: #f59e0b; font-weight: bold");
        store.recordToolCall({
          name: msg.name,
          arguments: msg.arguments,
          contract: msg.contract,
        });
        store.addToolActionToTranscript(
          {
            name: msg.name,
            arguments: msg.arguments,
            summary: msg.contract?.label,
          },
          msg.response_id || activeResponseId
        );
        break;

      case "tool_result":
        store.handleToolResult(msg);
        runtime.recordToolResult(msg);
        if (Array.isArray(msg.payload?.active_filters)) {
          store.activeFilters = msg.payload.active_filters;
        }
        break;

      case "session_ready":
        store.sessionReady = true;
        runtime.setPhase("ready");
        break;

      case "session_updated":
        store.setSessionInfo({
          mode: msg.mode,
          inputMode: msg.input_mode,
          turnDetection: msg.turn_detection,
          provider: msg.provider,
          model: msg.model,
          inputAudioRate: msg.input_audio_rate,
          outputAudioRate: msg.output_audio_rate,
        });
        window.__verbalvis_session_id = msg.session_id || "";
        analysisId = normalizeAnalysisId(msg.analysis_id) || analysisId;
        setCurrentAnalysisId(analysisId);
        break;

      case "error":
        runtime.setPhase("error", { toolRunning: false, tools: [] });
        runtime.recordToolResult({
          success: false,
          error: msg.message || "Realtime server error",
        });
        console.error("Server error:", msg.message);
        break;
    }
  }

  function _syncDashboardState(state = {}) {
    runtime.updateDashboardState(state);
    if (Array.isArray(state.filters)) {
      store.activeFilters = state.filters;
    }
    if (Array.isArray(state.highlighted)) {
      if (state.highlighted.length) {
        store.highlightViews(state.highlighted, null, true);
      } else {
        store.clearHighlight();
      }
    }
  }

  function sendAudio(base64pcm) {
    if (toolRunning.value) return;
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({ type: "audio", data: base64pcm }));
    } else {
      console.warn("sendAudio: socket not open, readyState =", socket.value?.readyState);
    }
  }

  function sendPlaybackStopped(responseId, reason, playbackCursor) {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({
        type: "playback_stopped",
        response_id: responseId,
        reason,
        playback_cursor: playbackCursor || null,
      }));
    }
  }

  function _stopAssistantPlayback(responseId, reason) {
    store.isAssistantSpeaking = false;
    suppressCurrentAssistantTranscript = false;
    const stoppedResponseId = responseId || activeResponseId;

    store.interruptAssistantResponse(stoppedResponseId);

    if (!responseId || activeResponseId === responseId) {
      activeResponseId = null;
    }

    let playbackCursor = null;
    if (audioPlayer?.stopAssistantAudio) {
      playbackCursor = audioPlayer.stopAssistantAudio({
        responseId: stoppedResponseId,
        reason,
        blockNewAudio: true,
      });
    } else if (audioPlayer?.stop) {
      playbackCursor = audioPlayer.stop();
    }

    sendPlaybackStopped(
      stoppedResponseId,
      reason || "assistant_playback_stop",
      playbackCursor
    );
  }

  function _handleUserTranscript(msg) {
    const utteranceId = msg.utterance_id || msg.item_id || null;
    const hasDelta = typeof msg.delta === "string";
    const text = hasDelta ? msg.delta : msg.text;
    const isPartial = msg.status === "partial" || msg.completed === false || msg.is_final === false || hasDelta;

    if (isPartial) {
      store.updateUserTranscript({
        utteranceId,
        text,
        status: "listening",
      });
      return;
    }

    store.completeUserTranscript(text, { utteranceId });
  }

  function disconnect() {
    manualClose = true;
    if (socket.value) {
      socket.value.close();
      socket.value = null;
    }
    activeResponseId = null;
    store.sessionReady = false;
    runtime.setPhase("disconnected", { toolRunning: false, tools: [] });
  }

  function reconnect() {
    disconnect();
    connect(lastUrl || undefined);
  }

  function getOrCreateAnalysisId() {
    const fromWindow = normalizeAnalysisId(window.__verbalvis_analysis_id);
    if (fromWindow) return fromWindow;

    const params = new URLSearchParams(window.location.search);
    const forceNew = ["1", "true", "yes", "on"].includes(
      String(params.get("new_analysis") || params.get("newAnalysis") || "").toLowerCase()
    );
    const fromUrl = normalizeAnalysisId(params.get("analysis_id") || params.get("analysisId"));
    const fromStorage = forceNew ? "" : normalizeAnalysisId(readStoredAnalysisId());
    const id = fromUrl || fromStorage || `analysis-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 10)}`;
    return setCurrentAnalysisId(id);
  }

  function normalizeAnalysisId(value) {
    return String(value || "").trim().replace(/[^A-Za-z0-9_.-]/g, "-").slice(0, 80);
  }

  function readStoredAnalysisId() {
    try {
      return window.localStorage?.getItem(ANALYSIS_ID_STORAGE_KEY) || "";
    } catch (_) {
      return "";
    }
  }

  function setCurrentAnalysisId(id) {
    window.__verbalvis_analysis_id = id;
    try {
      window.localStorage?.setItem(ANALYSIS_ID_STORAGE_KEY, id);
    } catch (_) {
      // Storage can be disabled in private modes; the in-memory id still works.
    }
    return id;
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
    reconnect,
  };
}
