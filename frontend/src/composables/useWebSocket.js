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

  function connect(url = `ws://${location.host}/ws`) {
    store.connectionStatus = "connecting";
    const ws = new WebSocket(url);
    socket.value = ws;

    ws.onopen = () => {
      store.connectionStatus = "connected";
    };

    ws.onclose = () => {
      store.connectionStatus = "disconnected";
      socket.value = null;
    };

    ws.onerror = () => {
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
        break;

      case "views_update":
        store.updateViews(msg.views);
        break;

      case "audio":
        store.isAssistantSpeaking = true;
        if (audioPlayer) {
          audioPlayer.enqueue(msg.data);
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
        // User barge-in: stop playback
        store.isAssistantSpeaking = false;
        assistantTranscriptBuffer = "";
        if (audioPlayer) {
          audioPlayer.stop();
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
      socket.value.send(JSON.stringify({ type: "start_session" }));
    }
  }

  function sendAudio(base64pcm) {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      console.log("mic chunk", base64pcm.length);
      socket.value.send(JSON.stringify({ type: "audio", data: base64pcm }));
    } else {
      console.warn("sendAudio: socket not open, readyState =", socket.value?.readyState);
    }
  }

  function disconnect() {
    if (socket.value) {
      socket.value.close();
      socket.value = null;
    }
  }

  onBeforeUnmount(disconnect);

  return { socket, connect, startSession, sendAudio, disconnect };
}
