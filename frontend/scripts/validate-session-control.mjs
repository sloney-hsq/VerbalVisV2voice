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
const runtimeStore = readFileSync(
  resolve(repoRoot, "frontend/src/stores/runtime.js"),
  "utf8",
);
const realtime = readFileSync(
  resolve(repoRoot, "backend/realtime.py"),
  "utf8",
);
const main = readFileSync(
  resolve(repoRoot, "backend/main.py"),
  "utf8",
);
const envExample = readFileSync(
  resolve(repoRoot, "backend/.env.example"),
  "utf8",
);

assert.match(
  dashboard,
  /onMounted\(\(\) => \{[\s\S]*ws\.connect\(\)/,
  "Opening the page must create one browser/backend/Qwen session.",
);
assert.match(
  dashboard,
  /async function startMicrophone\(\)[\s\S]*audio\.startRecording\(\(base64Pcm\) => ws\.sendAudio\(base64Pcm\)\)/,
  "Start mic must only begin PCM capture and transmission.",
);
assert.doesNotMatch(
  dashboard,
  /startMicrophone[\s\S]{0,500}ws\.(?:connect|startSession)\(/,
  "Start mic must not create another WebSocket or Qwen session.",
);
assert.match(
  dashboard,
  /if \(audio\.isRecording\.value\) audio\.stopRecording\(\)/,
  "Stop mic must pause capture without disconnecting the session.",
);
assert.doesNotMatch(
  dashboard,
  /toggleMicrophone[\s\S]{0,300}ws\.disconnect\(/,
  "Stopping the mic must not close the conversation session.",
);
assert.match(
  webSocket,
  /\[WebSocket\.OPEN, WebSocket\.CONNECTING\]\.includes\(socket\.value\.readyState\)/,
  "connect() must be idempotent within one page lifecycle.",
);
assert.doesNotMatch(
  webSocket,
  /start_session|startSession/,
  "The browser must not create a Qwen session on every mic click.",
);
assert.match(
  realtime,
  /await self\._connect_qwen\(\)[\s\S]*await self\._configure_qwen\(\)/,
  "The backend must create and configure Qwen when the page WebSocket opens.",
);
assert.doesNotMatch(
  realtime,
  /_wait_for_client_start|start_session/,
  "Qwen startup must not wait for a microphone-control event.",
);
assert.match(
  realtime,
  /def qwen_configuration_error\(/,
  "Qwen configuration must be validated explicitly.",
);
assert.match(
  realtime,
  /"type": "configuration_error"/,
  "Missing configuration must be reported once to the browser.",
);
assert.match(
  runtimeStore,
  /case "configuration_error":|configurationError/,
  "The UI runtime must preserve an actionable configuration state.",
);
assert.match(
  main,
  /qwen_configured/,
  "The health endpoint must expose whether Qwen is configured.",
);
assert.match(envExample, /^DASHSCOPE_API_KEY=/m);
assert.match(envExample, /^QWEN_WORKSPACE_ID=/m);
assert.match(envExample, /^QWEN_REGION=beijing/m);

console.log("One-session-per-page microphone validation: PASS");
