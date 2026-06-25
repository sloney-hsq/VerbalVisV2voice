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
  let reconnectTimer = null;
  let reconnectAttempts = 0;
  let manualClose = false;

  function connect(url = `ws://${location.host}/ws`) {
    if (
      socket.value &&
      (socket.value.readyState === WebSocket.OPEN || socket.value.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    manualClose = false;
    clearReconnectTimer();
    store.connectionStatus = "connecting";
    const ws = new WebSocket(url);
    socket.value = ws;

    ws.onopen = () => {
      reconnectAttempts = 0;
      store.connectionStatus = "connected";
      console.log("%c[WS] connected to backend", "color: #22c55e; font-weight: bold");
    };

    ws.onclose = () => {
      store.connectionStatus = "disconnected";
      socket.value = null;
      scheduleReconnect(url);
    };

    ws.onerror = (event) => {
      console.warn("[WS] backend connection error", event);
      store.connectionStatus = "disconnected";
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
        });
        break;

      case "views_update":
        store.updateViews(msg.views);
        break;

      case "audio":
        store.isAssistantSpeaking = true;
        if (audioPlayer) {
          audioPlayer.enqueue(msg.data, {
            item_id: msg.item_id,
            content_index: msg.content_index,
          });
        }
        break;

      case "transcript":
        if (msg.role === "assistant") {
          assistantTranscriptBuffer += msg.delta || "";
        } else if (msg.role === "user") {
          store.addTranscript("user", msg.text);
        }
        break;

      case "response_done":
        store.isAssistantSpeaking = false;
        if (assistantTranscriptBuffer.trim()) {
          store.addTranscript("assistant", assistantTranscriptBuffer.trim());
        }
        assistantTranscriptBuffer = "";
        if (audioPlayer) {
          audioPlayer.flush();
        }
        break;

      case "speech_started":
        if (store.inputMode === "open_mic") {
          // Server VAD owns barge-in only in open-mic mode. In local_vad/ptt,
          // the client has already stopped playback and sent truncate metadata.
          store.isAssistantSpeaking = false;
          assistantTranscriptBuffer = "";
          if (audioPlayer) {
            const cursor = audioPlayer.stop();
            truncateAssistantAudio(cursor);
          }
        }
        break;

      case "tool_call":
        console.log(`%c>>> TOOL CALL: ${msg.name}(${msg.arguments})`, "color: #f59e0b; font-weight: bold");
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
        });
        // Store session info for recording upload
        window.__verbalvis_session_id = msg.session_id || "";
        break;

      case "error":
        console.error("Server error:", msg.message);
        break;
    }
  }

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function scheduleReconnect(url) {
    if (manualClose || reconnectTimer) return;
    reconnectAttempts += 1;
    const delayMs = Math.min(3000, 500 * reconnectAttempts);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect(url);
    }, delayMs);
  }

  function startSession() {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      console.log("%c[WS] sending start_session", "color: #f59e