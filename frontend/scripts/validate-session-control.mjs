import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../..");
const dashboard = readFileSync(
  resolve(repoRoot, "frontend/src/components/Dashboard.vue"),
  "utf8",
);
const webSocket = readFileSync(
  resolve(repoRoot, "frontend/src/composables/useWebSocket.js"),
  "utf8",
);
const audio = readFileSync(
  resolve(repoRoot, "frontend/src/composables/useAudio.js"),
  "utf8",
);
const realtime = readFileSync(
  resolve(repoRoot, "backend/realtime.py"),
  "utf8",
);

assert.match(
  audio,
  /async function prepareRecording\(\)[\s\S]*await ensureCapture\(\)/,
  "Microphone permission/setup must be separable from audio transmission.",
);
assert.match(
  dashboard,
  /await audio\.prepareRecording\(\)[\s\S]*await ws\.startSession\(\)[\s\S]*await audio\.startRecording/,
  "A click must prepare the mic, start Qwen, then begin PCM transmission.",
);
assert.doesNotMatch(
  dashboard,
  /connectionStatus !== "connected"\s*\|\|\s*!store\.sessionReady/,
  "The Start mic button must remain available before Qwen session_ready.",
);
assert.match(
  webSocket,
  /function startSession\(\)[\s\S]*type:\s*"start_session"/,
  "The browser must explicitly request Qwen session startup.",
);
assert.match(
  webSocket,
  /case "session_ready":[\s\S]*resolveSessionStart/,
  "PCM capture must wait for backend session_ready.",
);
assert.match(
  webSocket,
  /if \(!dashboard\.sessionReady\) return false;/,
  "Audio must never be sent before Qwen is configured.",
);
assert.match(
  realtime,
  /await self\._wait_for_client_start\(\)[\s\S]*await self\._connect_qwen\(\)/,
  "Backend must wait for user start before connecting Qwen.",
);
assert.match(
  realtime,
  /async def _wait_for_client_start[\s\S]*start_session/,
  "Backend must recognize the explicit start_session control event.",
);

console.log("User-controlled realtime session validation: PASS");
