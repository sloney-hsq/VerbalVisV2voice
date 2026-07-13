import test from "node:test";
import assert from "node:assert/strict";

import { groupTranscriptItems } from "../src/transcriptGroups.js";

test("anchors actions after the final assistant message", () => {
  const [group] = groupTranscriptItems([
    { id: "user-1", role: "user", text: "Show me" },
    { id: "assistant-1", role: "assistant", text: "First response" },
    { id: "tool-1", role: "tool", summary: "create visual" },
    {
      id: "assistant-2",
      role: "assistant",
      text: "Interrupted",
      status: "interrupted",
    },
  ]);

  assert.equal(group.actionAnchorId, "assistant-2");
});

test("does not anchor actions to a user message when no assistant exists", () => {
  const [group] = groupTranscriptItems([
    { id: "user-1", role: "user", text: "Show me" },
    { id: "tool-1", role: "tool", summary: "create visual" },
  ]);

  assert.equal(group.actionAnchorId, null);
});

test("keeps a late tool action with the assistant response that started it", () => {
  const groups = groupTranscriptItems([
    { id: "user-1", role: "user", text: "First request" },
    {
      id: "assistant-1",
      role: "assistant",
      responseId: "response-1",
      text: "First response",
    },
    { id: "user-2", role: "user", text: "Second request" },
    {
      id: "tool-1",
      role: "tool",
      responseId: "response-1",
      summary: "create visual",
    },
  ]);

  assert.equal(groups[0].actionAnchorId, "assistant-1");
  assert.deepEqual(groups[0].actions.map((item) => item.id), ["tool-1"]);
  assert.deepEqual(groups[1].actions, []);
});
