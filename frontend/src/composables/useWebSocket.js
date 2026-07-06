import { ref, onBeforeUnmount } from "vue";
import { useDashboardStore } from "../stores/dashboard";

const ANALYSIS_ID_STORAGE_KEY = "verbalvis.analysisId";

/**
 * WebSocket composable – bridges frontend to VerbalVis backend.
 * Dispatches incoming messages to the Pinia store and audio player.
 */
export function useWebSocket(audioPlayer) {
  const store = useDashboardStore();
  const socket = ref(null);

  let suppressCurrentAssistantTranscript = false;
  let activeResponseId = null;
  let manualClose = false;
  let lastUrl = null;
  let analysisId = getOrCreateAnalysisId();

  function connect(url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?model=qwen3.5-omni-plus-realtime`) {
    if (
      socket.value &&
      (socket.value.readyState === WebSocket.OPEN || socket.value.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    manualClose = false;
    lastUrl = url;
    store.connectionStatus = "connecting";
    const ws = new WebSocket(url);
    socket.value = ws;

    ws.onopen = () => {
      store.connectionStatus = "connected";
      console.log("%c[WS] connected to backend", "color: #22c55e; font-weight: bold");
    };

    ws.onclose = () => {
      if (socket.value !== ws) return;
      store.connectionStatus = "disconnected";
      store.sessionReady = false;
      activeResponseId = null;
      socket.value = null;
    };

    ws.onerror = (event) => {
      if (socket.value !== ws) return;
      console.warn("[WS] backend connection error", event);
      store.connectionStatus = "disconnected";
      store.sessionReady = false;
      activeResponseId = null;
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
        store.setTextTurnProcessing(false);
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
        if (store.sessionMode === "turn_based_text") {
          store.setTextTurnProcessing(true);
        }
        store.beginAssistantResponse(msg.response_id);
        audioPlayer?.beginAssistantResponse?.(msg.response_id);
        break;

      case "views_update":
        store.updateViews(msg.views);
        break;

      case "audio":
        if (!msg.response_id || msg.response_id !== activeResponseId) {
          break;
        }
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
        store.setTextTurnProcessing(false);
        suppressCurrentAssistantTranscript = false;
        if (audioPlayer) {
          audioPlayer.flush({
            response_id: msg.response_id,
          });
        }
        activeResponseId = null;
        break;

      case "assistant_response_done":
        if (msg.response_id && msg.response_id === activeResponseId) {
          store.completeAssistantResponse(msg.response_id);
          activeResponseId = null;
        }
        store.setTextTurnProcessing(false);
        suppressCurrentAssistantTranscript = false;
        break;

      case "speech_started":
        if (msg.text || msg.utterance_id) {
          store.beginUserTranscript({
            utteranceId: msg.utterance_id,
            text: msg.text || "",
          });
        }
        break;

      case "assistant_playback_pause":
        store.isAssistantSpeaking = false;
        audioPlayer?.pauseAssistantAudio?.({
          responseId: msg.response_id || activeResponseId,
          reason: msg.reason || "assistant_playback_pause",
        });
        break;

      case "assistant_playback_resume":
        store.isAssistantSpeaking = true;
        audioPlayer?.resumeAssistantAudio?.({
          responseId: msg.response_id || activeResponseId,
          reason: msg.reason || "assistant_playback_resume",
        });
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

      case "tool_call":
        console.log(`%c>>> TOOL CALL: ${msg.name}(${msg.arguments})`, "color: #f59e0b; font-weight: bold");
        store.recordToolCall({ name: msg.name, arguments: msg.arguments });
        store.addToolActionToTranscript(
          { name: msg.name, arguments: msg.arguments },
          msg.response_id || activeResponseId
        );
        break;

      case "tool_result":
        store.handleToolResult(msg);
        break;

      case "session_ready":
        store.sessionReady = true;
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
        // Store session info for recording upload
        window.__verbalvis_session_id = msg.session_id || "";
        analysisId = normalizeAnalysisId(msg.analysis_id) || analysisId;
        setCurrentAnalysisId(analysisId);
        break;

      case "error":
        console.error("Server error:", msg.message);
        store.setTextTurnProcessing(false);
        break;

      case "turn_rejected":
        console.warn("Turn rejected:", msg.reason);
        if (msg.reason !== "assistant_busy") {
          store.setTextTurnProcessing(false);
        }
        break;
    }
  }

  function startSession() {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      console.log("%c[WS] sending start_session", "color: #f59e0b; font-weight: bold");
      store.sessionReady = false;
      socket.value.send(JSON.stringify({
        type: "start_session",
        analysis_id: analysisId,
      }));
    } else {
      console.error("[WS] cannot send start_session — socket not open, readyState:", socket.value?.readyState);
    }
  }

  function sendAudio(base64pcm) {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({ type: "audio", data: base64pcm }));
    } else {
      console.warn("sendAudio: socket not open, readyState =", socket.value?.readyState);
    }
  }

  function _stopAssistantPlayback(responseId, reason) {
    store.isAssistantSpeaking = false;
    suppressCurrentAssistantTranscript = false;
    store.interruptAssistantResponse(responseId || activeResponseId);
    if (!responseId || activeResponseId === responseId) {
      activeResponseId = null;
    }
    if (!audioPlayer) return;
    if (audioPlayer.stopAssistantAudio) {
      audioPlayer.stopAssistantAudio({
        responseId,
        reason,
        blockNewAudio: true,
      });
    } else {
      audioPlayer.stop();
    }
  }

  function sendText(text) {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      const turnId = `text-turn-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      socket.value.send(JSON.stringify({
        type: "user_text",
        text,
        turn_id: turnId,
        condition: "turn_based_text",
        analysis_id: analysisId,
        timestamp: performance.now(),
      }));
      return turnId;
    }
    console.warn("sendText: socket not open, readyState =", socket.value?.readyState);
    return null;
  }

  function interruptActiveResponse(reason = "user_superseded_response") {
    if (!activeResponseId) return;
    _stopAssistantPlayback(activeResponseId, reason);
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

  function truncateAssistantAudio(assistantAudio) {
    if (!assistantAudio?.item_id) return;
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({ type: "truncate_assistant_audio", assistant_audio: assistantAudio }));
    }
  }

  function disconnect() {
    manualClose = true;
    if (socket.value) {
      socket.value.close();
      socket.value = null;
    }
    activeResponseId = null;
    store.sessionReady = false;
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
    connect,
    startSession,
    truncateAssistantAudio,
    sendAudio,
    sendText,
    interruptActiveResponse,
    disconnect,
    reconnect,
  };
}
