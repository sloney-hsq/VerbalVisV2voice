import { ref } from "vue";

/**
 * Screen + audio recorder.
 * Captures the current tab (video + system audio) plus microphone input.
 * Saves as WebM and uploads to backend on stop.
 */
export function useScreenRecorder() {
  const isScreenRecording = ref(false);

  let mediaRecorder = null;
  let recordedChunks = [];
  let displayStream = null;
  let combinedStream = null;

  /**
   * Start recording the current tab + mic audio.
   * @param {MediaStream|null} micStream - existing mic MediaStream to mix in
   */
  async function startScreenRecording(micStream = null) {
    try {
      // Capture current tab with system audio
      displayStream = await navigator.mediaDevices.getDisplayMedia({
        video: { displaySurface: "browser" },
        audio: true, // captures tab audio (AI voice)
      });

      // Combine display + mic audio tracks
      const tracks = [...displayStream.getTracks()];
      if (micStream) {
        for (const t of micStream.getAudioTracks()) {
          tracks.push(t);
        }
      }
      combinedStream = new MediaStream(tracks);

      recordedChunks = [];
      mediaRecorder = new MediaRecorder(combinedStream, {
        mimeType: "video/webm;codecs=vp9,opus",
      });

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        _uploadRecording();
      };

      // Stop if user stops sharing via browser UI
      displayStream.getVideoTracks()[0].onended = () => {
        stopScreenRecording();
      };

      mediaRecorder.start(1000); // chunk every 1s
      isScreenRecording.value = true;
      console.log("Screen recording started");
    } catch (err) {
      console.error("Failed to start screen recording:", err);
    }
  }

  function stopScreenRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    if (displayStream) {
      displayStream.getTracks().forEach((t) => t.stop());
      displayStream = null;
    }
    combinedStream = null;
    isScreenRecording.value = false;
    console.log("Screen recording stopped");
  }

  async function _uploadRecording() {
    if (!recordedChunks.length) return;

    const blob = new Blob(recordedChunks, { type: "video/webm" });
    recordedChunks = [];

    // Also download locally as fallback
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `verbalvis_${new Date().toISOString().replace(/[:.]/g, "-")}.webm`;
    // Don't auto-download, just upload to backend

    const formData = new FormData();
    formData.append("file", blob, "screen_recording.webm");
    // Try to get session_id from the page (set by WS init)
    formData.append("session_id", window.__verbalvis_session_id || "");

    try {
      const resp = await fetch(`http://${location.host}/upload-recording`, {
        method: "POST",
        body: formData,
      });
      const result = await resp.json();
      console.log("Screen recording uploaded:", result);
    } catch (err) {
      console.error("Failed to upload recording, saving locally:", err);
      a.click(); // fallback: download in browser
    }
    URL.revokeObjectURL(url);
  }

  return {
    isScreenRecording,
    startScreenRecording,
    stopScreenRecording,
  };
}
