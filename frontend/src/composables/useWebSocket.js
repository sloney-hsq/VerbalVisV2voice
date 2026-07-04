import { ref, onBeforeUnmount } from "vue";
import { useDashboardStore } from "../stores/dashboard";

/**
 * WebSocket composable – bridges frontend to VerbalVis backend.
 * Dispatches incoming messages to the Pinia store and audio player.
 */
export function useWebSocket(audioPlayer) {
  const store = useDashboardStore();
  const socket = ref(null);

  let assistantTranscriptBuffer = "";
  let suppressCurrentAssistantTranscript = false;
  let manualClose = false;
  let lastUrl = null;

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
      store.connectionStatus = "disconnected";
      store.sessionReady = false;
      if (socket.value === ws) {
        socket.value = null;
      }
    };

    ws.onerror = (event) => {
      console.warn("[WS] backend connection error", event);
      store.connectionStatus = "disconnected";
      store.sessionReady = false;
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      _dispatch(msg);
    };
  }

  function _dispatch(msg) {
    switch (msg.type) {
      case "init":
        store.initViews(msg.views);
        store.setSessionInfo({
          mode: msg.mode,
          inputMode: msg.input_mode,
          provider: msg.provider,
          model: msg.model,
          inputAudioRate: msg.input_audio_rate,
          outputAudioRate: msg.output_audio_rate,
        });
        break;

      case "views_update":
        store.updateViews(msg.views);
        break;

      case "session_summary":
        store.addSessionSummary(msg);
        break;

      case "audio":
        store.isAssistantSpeaking = true;
        if (audioPlayer) {
          audioPlayer.enqueue(msg.data, {
            response_id: msg.response_id,
            item_id: msg.item_id,
            content_index: msg.content_index,
            sample_rate: msg.sample_rate,
          });
        }
        break;

      case "transcript":
        if (msg.role === "assistant") {
          if (!suppressCurrentAssistantTranscript) {
            assistantTranscriptBuffer += msg.delta || "";
          }
        } else if (msg.role === "user") {
          store.addTranscript("user", msg.text);
        }
        break;

      case "suppress_assistant_buffer":
        assistantTranscriptBuffer = "";
        suppressCurrentAssistantTranscript = true;
        break;

      case "response_done":
        store.isAssistantSpeaking = false;
        if (!suppressCurrentAssistantTranscript && assistantTranscriptBuffer.trim()) {
          store.addTranscript("assistant", assistantTranscriptBuffer.trim());
        }
        assistantTranscriptBuffer = "";
        suppressCurrentAssistantTranscript = false;
        if (audioPlayer) {
          audioPlayer.flush();
        }
        break;

      case "speech_started":
        if (msg.invalidated_response_id) {
          store.isAssistantSpeaking = false;
          assistantTranscriptBuffer = "";
          suppressCurrentAssistantTranscript = false;
          if (audioPlayer) {
            if (audioPlayer.stopAssistantAudio) {
              audioPlayer.stopAssistantAudio({
                responseId: msg.invalidated_response_id,
                reason: "speech_started",
              });
            } else {
              audioPlayer.stop();
            }
          }
        }
        break;

      case "tool_call":
        console.log(`%c>>> TOOL CALL: ${msg.name}(${msg.arguments})`, "color: #f59e0b; font-weight: bold");
        store.recordToolCall({ name: msg.name, arguments: msg.arguments });
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
        break;
    }
  }

  function startSession() {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      console.log("%c[WS] sending start_session", "color: #f59e0b; font-weight: bold");
      store.sessionReady = false;
      socket.value.send(JSON.stringify({ type: "start_session" }));
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

  function notifyLocalSpeechStarted() {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({ type: "local_speech_started" }));
    }
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
    store.sessionReady = false;
  }

  function reconnect() {
    disconnect();
    connect(lastUrl || undefined);
  }

  onBeforeUnmount(disconnect);

  return {
    socket,
    connect,
    startSession,
    truncateAssistantAudio,
    sendAudio,
    notifyLocalSpeechStarted,
    disconnect,
    reconnect,
  };
}
