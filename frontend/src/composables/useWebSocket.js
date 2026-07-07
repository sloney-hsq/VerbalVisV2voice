import { ref, onBeforeUnmount } from "vue";
import { useDashboardStore } from "../stores/dashboard";

/**
 * WebSocket composable – bridges frontend to VerbalVis backend.
 * Dispatches incoming messages to the Pinia store and audio player.
 */
export function useWebSocket(audioPlayer, options = {}) {
  const store = useDashboardStore();
  const socket = ref(null);

  let suppressCurrentAssistantTranscript = false;
  let activeResponseId = null;
  let activeResponseTurnId = null;
  let latestUserTurnId = null;
  let userSpeechActive = false;
  let manualClose = false;
  let lastUrl = null;
  let analysisId = normalizeAnalysisId(options.analysisId) || getOrCreateAnalysisId();

  function currentAnalysisId() {
    const configured = normalizeAnalysisId(options.getAnalysisId?.());
    if (configured) {
      analysisId = configured;
    }
    return analysisId;
  }

  function connect(url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?model=qwen3.5-omni-plus-realtime`) {
    if (
      socket.value &&
      (socket.value.readyState === WebSocket.OPEN || socket.value.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    manualClose = false;
    lastUrl = withAnalysisId(url);
    store.connectionStatus = "connecting";
    const ws = new WebSocket(lastUrl);
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
        activeResponseTurnId = null;
        latestUserTurnId = null;
        userSpeechActive = false;
        store.setTextTurnProcessing(false);
        store.initViews(msg.views, { activeFilters: msg.active_filters });
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
        if (_isStaleTurn(msg.turn_id)) {
          _stopAssistantPlayback(msg.response_id, "stale_turn_response_started");
          break;
        }
        activeResponseId = msg.response_id;
        activeResponseTurnId = msg.turn_id || null;
        suppressCurrentAssistantTranscript = false;
        if (store.sessionMode === "turn_based_text") {
          store.setTextTurnProcessing(true);
        }
        store.beginAssistantResponse(msg.response_id);
        audioPlayer?.beginAssistantResponse?.(msg.response_id);
        break;

      case "views_update":
        if (!msg.committed && _isStaleTurn(msg.turn_id)) break;
        store.updateViews(msg.views);
        break;

      case "audio":
        if (!msg.response_id || msg.response_id !== activeResponseId) {
          break;
        }
        if (_isStaleTurn(msg.turn_id) || !_matchesActiveResponseTurn(msg.turn_id)) {
          break;
        }
        if (audioPlayer) {
          const didEnqueue = audioPlayer.enqueue(msg.data, {
            response_id: msg.response_id,
            turn_id: msg.turn_id,
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
          if (_isStaleTurn(msg.turn_id) || !_matchesActiveResponseTurn(msg.turn_id)) {
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
        if (_isStaleTurn(msg.turn_id)) break;
        suppressCurrentAssistantTranscript = true;
        store.suppressAssistantResponse(msg.response_id || activeResponseId);
        break;

      case "response_done":
        if (!msg.response_id || msg.response_id !== activeResponseId) {
          break;
        }
        if (_isStaleTurn(msg.turn_id) || !_matchesActiveResponseTurn(msg.turn_id)) {
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
        activeResponseTurnId = null;
        break;

      case "assistant_response_done":
        if (
          msg.response_id &&
          msg.response_id === activeResponseId &&
          !_isStaleTurn(msg.turn_id) &&
          _matchesActiveResponseTurn(msg.turn_id)
        ) {
          store.completeAssistantResponse(msg.response_id);
          activeResponseId = null;
          activeResponseTurnId = null;
        }
        store.setTextTurnProcessing(false);
        suppressCurrentAssistantTranscript = false;
        break;

      case "speech_started":
        _markUserSpeechStarted(msg.turn_id || msg.utterance_id);
        store.beginUserTranscript({
          utteranceId: latestUserTurnId,
          text: msg.text || "",
        });
        break;

      case "speech_stopped":
        if (!msg.turn_id || msg.turn_id === latestUserTurnId) {
          userSpeechActive = false;
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
        if (_isStaleTurn(msg.turn_id) || !_matchesActiveResponseTurn(msg.turn_id)) break;
        console.log(`%c>>> TOOL CALL: ${msg.name}(${msg.arguments})`, "color: #f59e0b; font-weight: bold");
        store.recordToolCall({ name: msg.name, arguments: msg.arguments });
        if (!msg.committed) {
          store.addToolActionToTranscript(
            { name: msg.name, arguments: msg.arguments },
            msg.response_id || activeResponseId
          );
        }
        break;

      case "tool_result":
        if (!msg.committed && (
          _isStaleTurn(msg.turn_id) || !_matchesActiveResponseTurn(msg.turn_id)
        )) break;
        store.handleToolResult(msg);
        break;

      case "tool_execution_committed":
      case "tool_execution_started":
      case "tool_execution_completed":
      case "tool_batch_completed":
        store.upsertToolTimelineEvent(msg);
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
        analysis_id: currentAnalysisId(),
      }));
    } else {
      console.error("[WS] cannot send start_session — socket not open, readyState:", socket.value?.readyState);
    }
  }

  function sendAudio(base64pcm) {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({
        type: "audio",
        data: base64pcm,
        analysis_id: currentAnalysisId(),
      }));
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
      activeResponseTurnId = null;
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
        analysis_id: currentAnalysisId(),
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

  function _markUserSpeechStarted(turnId = null) {
    latestUserTurnId = turnId || latestUserTurnId || `voice-turn-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    userSpeechActive = true;
    return latestUserTurnId;
  }

  function _handleUserTranscript(msg) {
    if (_isStaleTurn(msg.turn_id)) return;
    if (msg.turn_id) latestUserTurnId = msg.turn_id;
    const utteranceId = msg.utterance_id || msg.turn_id || msg.item_id || null;
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
    activeResponseTurnId = null;
    userSpeechActive = false;
    store.sessionReady = false;
  }

  function sendAssistantPlaybackCompleted(responseId) {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({
        type: "assistant_playback_completed",
        response_id: responseId || null,
        analysis_id: currentAnalysisId(),
      }));
    }
  }

  function _isStaleTurn(turnId) {
    if (!latestUserTurnId) return false;
    return Boolean(turnId) && turnId !== latestUserTurnId;
  }

  function _matchesActiveResponseTurn(turnId) {
    if (!activeResponseTurnId) {
      return !latestUserTurnId || !turnId;
    }
    return !turnId || turnId === activeResponseTurnId;
  }

  function reconnect() {
    disconnect();
    connect(lastUrl || undefined);
  }

  function getOrCreateAnalysisId() {
    const fromWindow = normalizeAnalysisId(window.__verbalvis_analysis_id);
    if (fromWindow) return fromWindow;

    const params = new URLSearchParams(window.location.search);
    const fromUrl = normalizeAnalysisId(params.get("analysis_id") || params.get("analysisId"));
    const id = fromUrl || `session-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 10)}`;
    return setCurrentAnalysisId(id);
  }

  function normalizeAnalysisId(value) {
    return String(value || "").trim().replace(/[^A-Za-z0-9_.-]/g, "-").slice(0, 80);
  }

  function setCurrentAnalysisId(id) {
    window.__verbalvis_analysis_id = id;
    return id;
  }

  function withAnalysisId(rawUrl) {
    const url = new URL(rawUrl, window.location.href);
    if (url.protocol === "http:") url.protocol = "ws:";
    if (url.protocol === "https:") url.protocol = "wss:";
    url.searchParams.set("analysis_id", currentAnalysisId());
    return url.toString();
  }

  onBeforeUnmount(disconnect);

  return {
    socket,
    connect,
    startSession,
    truncateAssistantAudio,
    sendAudio,
    sendText,
    sendAssistantPlaybackCompleted,
    interruptActiveResponse,
    disconnect,
    reconnect,
  };
}
