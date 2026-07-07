import { ref, onBeforeUnmount } from "vue";
import { useDashboardStore } from "../stores/dashboard";

const ANALYSIS_ID_STORAGE_KEY = "verbalvis.analysisId";

/**
 * WebSocket composable bridges frontend to VerbalVis backend.
 * Dispatches incoming messages to the Pinia store and audio player.
 */
export function useWebSocket(audioPlayer) {
  const store = useDashboardStore();
  const socket = ref(null);

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
          conditionCode: msg.condition_code,
          provider: msg.provider,
          model: msg.model,
          inputAudioRate: msg.input_audio_rate,
          outputAudioRate: msg.output_audio_rate,
        });
        break;

      case "assistant_response_started":
        if (!msg.response_id) break;
        activeResponseId = msg.response_id;
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
          store.appendAssistantTranscript(msg.response_id, msg.delta || "");
        } else if (msg.role === "user") {
          _handleUserTranscript(msg);
        }
        break;

      case "assistant_transcript_done":
        if (!msg.response_id || msg.response_id !== activeResponseId) {
          break;
        }
        store.setAssistantTranscript(msg.response_id, msg.text || "");
        break;

      case "response_done":
        if (!msg.response_id || msg.response_id !== activeResponseId) {
          break;
        }
        store.completeAssistantResponse(msg.response_id);
        store.setTextTurnProcessing(false);
        activeResponseId = null;
        break;

      case "speech_started":
        if (msg.text || msg.utterance_id) {
          store.beginUserTranscript({
            utteranceId: msg.utterance_id,
            text: msg.text || "",
          });
        }
        break;

      case "assistant_playback_stop":
        _stopAssistantPlayback(msg.response_id, msg.reason || "assistant_playback_stop");
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
          conditionCode: msg.condition_code,
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

  function sendAudio(base64pcm) {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({
        type: "audio",
        data: base64pcm,
      }));
    } else {
      console.warn("sendAudio: socket not open, readyState =", socket.value?.readyState);
    }
  }

  function _stopAssistantPlayback(responseId, reason) {
    store.isAssistantSpeaking = false;
    store.interruptAssistantResponse(responseId || activeResponseId);
    if (!responseId || activeResponseId === responseId) {
      activeResponseId = null;
    }

    if (!audioPlayer) return;

    let result = null;
    if (audioPlayer.stopAssistantAudio) {
      result = audioPlayer.stopAssistantAudio({
        responseId,
        blockNewAudio: true,
      });
    } else if (audioPlayer.stop) {
      const cursor = audioPlayer.stop();
      result = {
        stopped: true,
        cursor,
      };
    }

    if (
      result?.stopped &&
      socket.value &&
      socket.value.readyState === WebSocket.OPEN
    ) {
      socket.value.send(JSON.stringify({
        type: "playback_stopped",
        response_id: responseId,
        reason,
        playback_cursor: result.cursor || null,
        client_wall_time_ms: Date.now(),
      }));
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
        condition_code: "text_cva",
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
    sendAudio,
    sendText,
    interruptActiveResponse,
    disconnect,
    reconnect,
  };
}
