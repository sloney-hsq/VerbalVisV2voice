import assert from "node:assert/strict";
import { groupTranscriptItems } from "../src/transcriptGroups.js";

const items = [
  { id: "u1", role: "user", text: "Compare SP", startedAt: 1 },
  { id: "t1", role: "tool", toolName: "update_analysis_scope", startedAt: 2 },
  { id: "t2", role: "tool", toolName: "compare_category_metrics", startedAt: 3 },
  { id: "a1", role: "assistant", text: "SP is ready", startedAt: 4 },
  { id: "u2", role: "user", text: "Now RJ", startedAt: 5 },
  { id: "a2", role: "assistant", text: "Switching to RJ", startedAt: 6 },
  { id: "t3", role: "tool", toolName: "compare_category_metrics", startedAt: 7 },
];

const groups = groupTranscriptItems(items);

assert.equal(groups.length, 2);
assert.equal(groups[0].id, "turn-u1");
assert.deepEqual(groups[0].messages.map((item) => item.id), ["u1", "a1"]);
assert.deepEqual(groups[0].actions.map((item) => item.id), ["t1", "t2"]);
assert.deepEqual(groups[1].messages.map((item) => item.id), ["u2", "a2"]);
assert.deepEqual(groups[1].actions.map((item) => item.id), ["t3"]);

const orphan = groupTranscriptItems([
  { id: "t0", role: "tool", toolName: "inspect_visual", startedAt: 1 },
  { id: "a0", role: "assistant", text: "Existing state", startedAt: 2 },
]);
assert.equal(orphan.length, 1);
assert.equal(orphan[0].id, "turn-session-start");
assert.deepEqual(orphan[0].messages.map((item) => item.id), ["a0"]);
assert.deepEqual(orphan[0].actions.map((item) => item.id), ["t0"]);

console.log("Transcript grouping validation: PASS");
