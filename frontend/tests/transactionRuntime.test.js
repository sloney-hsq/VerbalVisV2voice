import test from "node:test";
import assert from "node:assert/strict";

import { createPinia, setActivePinia } from "pinia";

import { dispatchTransactionalMessage } from "../src/composables/useWebSocket.js";
import { useDashboardStore } from "../src/stores/dashboard.js";
import { useRuntimeStore } from "../src/stores/runtime.js";

function createHarness() {
  setActivePinia(createPinia());
  const dashboard = useDashboardStore();
  const runtime = useRuntimeStore();
  const captureBlocks = [];
  const stoppedResponses = [];
  const audioPlayer = {
    setCaptureBlocked(blocked) {
      captureBlocks.push(Boolean(blocked));
    },
  };
  const stopAssistantPlayback = (responseId, reason) => {
    stoppedResponses.push({ responseId, reason });
  };

  function dispatch(message) {
    return dispatchTransactionalMessage(message, {
      dashboard,
      runtime,
      audioPlayer,
      stopAssistantPlayback,
    });
  }

  return {
    dashboard,
    runtime,
    captureBlocks,
    stoppedResponses,
    dispatch,
  };
}

test("keeps playback alive while overlap feedback is pending and clears it on resume", () => {
  const harness = createHarness();

  assert.equal(harness.dispatch({
    type: "response_overlap",
    response_id: "response-7",
    utterance_id: "utterance-2",
    intent_epoch: 4,
    status: "overlap_pending",
  }), true);
  assert.equal(harness.runtime.overlapPending, true);
  assert.equal(harness.runtime.responseStatus, "overlap_pending");
  assert.equal(harness.runtime.relevantResponseId, "response-7");
  assert.deepEqual(harness.stoppedResponses, []);

  assert.equal(harness.dispatch({
    type: "response_resumed",
    response_id: "response-7",
    intent_epoch: 4,
    decision: "backchannel",
  }), true);
  assert.equal(harness.runtime.overlapPending, false);
  assert.equal(harness.runtime.responseStatus, "streaming");
  assert.equal(harness.runtime.relevantResponseId, "response-7");
  assert.deepEqual(harness.stoppedResponses, []);
});

test("stops only the response identified as superseded", () => {
  const harness = createHarness();
  harness.dispatch({
    type: "response_overlap",
    response_id: "response-old",
    utterance_id: "utterance-new",
    intent_epoch: 8,
    status: "overlap_pending",
  });

  assert.equal(harness.dispatch({
    type: "response_superseded",
    response_id: "response-old",
    intent_epoch: 9,
    reason: "analytical_revision",
  }), true);
  assert.equal(harness.runtime.overlapPending, false);
  assert.equal(harness.runtime.responseStatus, "superseded");
  assert.equal(harness.runtime.relevantResponseId, "response-old");
  assert.deepEqual(harness.stoppedResponses, [{
    responseId: "response-old",
    reason: "analytical_revision",
  }]);
});

test("rejects a stale dashboard commit without changing revision or views", () => {
  const harness = createHarness();
  harness.dashboard.initViews(
    [{ id: "view-1", title: "Committed view", revision: 3 }],
    3,
    { filters: [{ field: "state", values: ["SP"] }] },
  );

  assert.equal(harness.dispatch({
    type: "dashboard_commit",
    commit_status: "stale_discarded",
    discard_reason: "intent_epoch_mismatch",
    dashboard_revision: 4,
    views: [{ id: "view-stale", title: "Must not appear", revision: 4 }],
    state: { filters: [{ field: "state", values: ["RJ"] }] },
  }), true);

  assert.equal(harness.dashboard.dashboardRevision, 3);
  assert.deepEqual(harness.dashboard.views.map((view) => view.id), ["view-1"]);
  assert.deepEqual(harness.dashboard.activeFilters, [
    { field: "state", values: ["SP"] },
  ]);
  assert.equal(harness.runtime.lastCommitStatus, "stale_discarded");
  assert.equal(harness.runtime.lastDiscardReason, "intent_epoch_mismatch");
});

test("applies an explicitly committed dashboard snapshot", () => {
  const harness = createHarness();
  harness.dashboard.initViews(
    [{ id: "view-1", title: "Old", revision: 1 }],
    1,
    {},
  );

  assert.equal(harness.dispatch({
    type: "dashboard_commit",
    commit_status: "committed",
    dashboard_revision: 2,
    views: [{ id: "view-2", title: "Committed", revision: 2 }],
    state: { filters: [{ field: "state", values: ["RJ"] }] },
  }), true);

  assert.equal(harness.dashboard.dashboardRevision, 2);
  assert.deepEqual(harness.dashboard.views.map((view) => view.id), ["view-2"]);
  assert.deepEqual(harness.runtime.dashboardState.filters, [
    { field: "state", values: ["RJ"] },
  ]);
  assert.equal(harness.runtime.lastCommitStatus, "committed");
});

test("tool batches update runtime feedback without blocking microphone capture", () => {
  const harness = createHarness();

  assert.equal(harness.dispatch({
    type: "tool_execution_started",
    response_id: "response-tools",
    changes_dashboard: true,
    tools: [{ name: "create_visual", label: "Create visual" }],
  }), true);
  assert.equal(harness.runtime.toolRunning, true);
  assert.deepEqual(harness.captureBlocks, []);

  assert.equal(harness.dispatch({
    type: "tool_execution_finished",
    response_id: "response-tools",
    commit_status: "committed",
    followup_requested: true,
    duration_ms: 18,
  }), true);
  assert.equal(harness.runtime.toolRunning, false);
  assert.equal(harness.runtime.lastCommitStatus, "committed");
  assert.deepEqual(harness.captureBlocks, []);
});

test("preserves legacy terminal tool diagnostics alongside commit status", () => {
  const harness = createHarness();

  harness.dispatch({
    type: "tool_execution_finished",
    response_id: "response-tools",
    commit_status: "failed",
    followup_requested: false,
    duration_ms: 27,
    fatal_error: "warehouse unavailable",
  });

  assert.equal(harness.runtime.lastToolDurationMs, 27);
  assert.equal(harness.runtime.lastToolError, "warehouse unavailable");
  assert.equal(harness.runtime.lastCommitStatus, "failed");
});
