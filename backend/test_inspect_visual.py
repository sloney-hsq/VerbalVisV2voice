from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any, cast
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import db
import tools
from realtime_qwen import MODEL_ONLY_TOOLS, MUTATING_TOOLS, QwenRealtimeSession, _qwen_tool_schemas


class DummyWebSocket:
    async def send_json(self, msg: dict) -> None:
        self.last_msg = msg


class InspectVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.initialize_db()

    def setUp(self) -> None:
        tools.init_views()

    def test_schema_and_view_id_normalization(self) -> None:
        schema = next(item for item in tools.TOOL_SCHEMAS if item["name"] == "inspect_visual")

        self.assertEqual(schema["parameters"]["required"], ["view_id"])
        self.assertEqual(set(schema["parameters"]["properties"]), {"view_id"})
        self.assertEqual(
            tools.normalize_tool_arguments("inspect_visual", {"view_id": "视图一"})["view_id"],
            "view-1",
        )
        self.assertEqual(
            tools.normalize_tool_arguments("inspect_visual", {"view_id": "图五"})["view_id"],
            "view-5",
        )

    def test_inspect_base_view_is_read_only(self) -> None:
        before_filters = copy.deepcopy(tools.active_filters)
        before_views = copy.deepcopy(tools.views)
        before_highlighted = copy.deepcopy(tools.highlighted_views)

        with mock.patch.object(tools, "_refresh_all_views", side_effect=AssertionError("refresh")):
            result = tools.execute_tool("inspect_visual", {"view_id": "view-1"})

        self.assertTrue(result["success"])
        payload = result["payload"]
        self.assertEqual(payload["view_id"], "view-1")
        self.assertEqual(payload["chart_type"], "line")
        self.assertIn("peak_value", payload["statistics"])
        self.assertEqual(payload["data"], before_views[0]["data"])
        self.assertEqual(payload["returned_data_points"], len(before_views[0]["data"]))
        self.assertFalse(payload["truncated"])
        self.assertEqual(tools.active_filters, before_filters)
        self.assertEqual(tools.views, before_views)
        self.assertEqual(tools.highlighted_views, before_highlighted)

    def test_unknown_view_returns_available_ids(self) -> None:
        result = tools.execute_tool("inspect_visual", {"view_id": "view-999"})

        self.assertFalse(result["success"])
        self.assertIn("Available: view-1, view-2, view-3, view-4", result["error"])

    def test_realtime_state_has_metadata_not_chart_contents(self) -> None:
        state = tools.realtime_state()
        text = tools.context_text()

        self.assertIn("views", state)
        for view in state["views"]:
            self.assertIn("id", view)
            self.assertIn("title", view)
            self.assertIn("type", view)
            self.assertIn("x", view)
            self.assertIn("y", view)
            self.assertNotIn("data", view)
            self.assertNotIn("statistics", view)
        self.assertNotIn("peak_value", text)
        self.assertNotIn("top_state_count", text)
        self.assertNotIn("data=", text)

    def test_append_visual_can_be_inspected_with_local_filters_and_freeze(self) -> None:
        created = tools.execute_tool(
            "append_visual",
            {
                "chart_type": "bar",
                "x": "customer_state",
                "y": "order_count",
                "title": "SP Orders Snapshot",
                "filters": [{"field": "customer_state", "operator": "eq", "value": "SP"}],
                "inherit_global_filters": False,
                "freeze": True,
            },
        )
        self.assertTrue(created["success"])

        inspected = tools.execute_tool(
            "inspect_visual",
            {"view_id": created["payload"]["view_id"]},
        )

        payload = inspected["payload"]
        self.assertEqual(payload["filter_scope"], "frozen_snapshot")
        self.assertEqual(payload["local_filters"], [{"field": "customer_state", "operator": "eq", "value": "SP"}])
        self.assertEqual(payload["effective_filters"], payload["snapshot_filters"])
        self.assertEqual(payload["data"], tools.views[-1]["data"])

    def test_large_non_scatter_view_is_truncated_to_sixty_rows(self) -> None:
        created = tools.execute_tool(
            "append_visual",
            {
                "chart_type": "bar",
                "x": "order_date",
                "y": "order_count",
                "title": "Orders by Date",
            },
        )
        self.assertTrue(created["success"])

        inspected = tools.execute_tool("inspect_visual", {"view_id": created["payload"]["view_id"]})
        payload = inspected["payload"]

        self.assertGreater(payload["total_data_points"], tools.MAX_INSPECT_ROWS)
        self.assertEqual(payload["returned_data_points"], tools.MAX_INSPECT_ROWS)
        self.assertTrue(payload["truncated"])

    def test_scatter_returns_summary_and_small_sample(self) -> None:
        created = tools.execute_tool(
            "append_visual",
            {
                "chart_type": "scatter",
                "x": "delivery_days",
                "y": "review_score",
                "title": "Delivery Days by Review Score",
            },
        )
        self.assertTrue(created["success"])

        inspected = tools.execute_tool("inspect_visual", {"view_id": created["payload"]["view_id"]})
        payload = inspected["payload"]

        self.assertIn("scatter_summary", payload)
        self.assertIn("sample_size", payload["scatter_summary"])
        self.assertIn("x_min", payload["scatter_summary"])
        self.assertIn("y_mean", payload["scatter_summary"])
        self.assertIn("correlation", payload["scatter_summary"])
        self.assertLessEqual(len(payload["data_sample"]), tools.MAX_SCATTER_SAMPLE_ROWS)
        self.assertNotIn("data", payload)

    def test_realtime_output_keeps_inspect_model_only(self) -> None:
        result = tools.execute_tool("inspect_visual", {"view_id": "view-3"})
        session = QwenRealtimeSession(cast(Any, DummyWebSocket()))
        output = json.loads(session._tool_result_text(result))

        self.assertIn("inspect_visual", MODEL_ONLY_TOOLS)
        self.assertNotIn("inspect_visual", MUTATING_TOOLS)
        qwen_tool_names = [item["function"]["name"] for item in _qwen_tool_schemas()]
        self.assertIn("inspect_visual", qwen_tool_names)
        self.assertEqual(output["tool"], "inspect_visual")
        self.assertIn("visual", output)
        self.assertIn("statistics", output["visual"])
        self.assertIn("data", output["visual"])
        self.assertNotIn("state", output)


if __name__ == "__main__":
    unittest.main()
