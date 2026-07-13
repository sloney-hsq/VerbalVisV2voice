import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import db
import tools


class ViewTitleBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.initialize_db()

    def setUp(self):
        self._tool_state = {
            "active_filters": tools.active_filters,
            "views": tools.views,
            "highlighted_views": tools.highlighted_views,
            "highlight_element": tools.highlight_element,
            "dim_others": tools.dim_others,
            "view_counter": tools.view_counter,
            "dashboard_revision": tools.dashboard_revision,
            "_history": tools._history,
        }
        tools.active_filters = []
        tools.views = []
        tools.highlighted_views = []
        tools.highlight_element = None
        tools.dim_others = True
        tools.view_counter = tools.BASE_VIEW_COUNT
        tools.dashboard_revision = 0
        tools._history = []

    def tearDown(self):
        for name, value in self._tool_state.items():
            setattr(tools, name, value)

    def test_create_schema_does_not_require_title(self):
        schema = next(
            item for item in tools.TOOL_SCHEMAS
            if item["name"] == "create_visual"
        )
        self.assertNotIn("title", schema["parameters"]["required"])

    def test_create_visual_generates_title_when_missing_or_empty(self):
        for requested_title in (None, ""):
            with self.subTest(requested_title=requested_title):
                args = {
                    "chart_type": "line",
                    "x": "order_week",
                    "y": "order_count",
                }
                if requested_title is not None:
                    args["title"] = requested_title

                result = tools.execute_tool("create_visual", args)

                self.assertTrue(result["success"], result)
                self.assertEqual(
                    result["payload"]["view"]["title"],
                    "Weekly Orders",
                )

    def test_update_visual_preserves_title_when_omitted(self):
        created = tools.execute_tool(
            "create_visual",
            {
                "chart_type": "line",
                "x": "order_week",
                "y": "order_count",
                "title": "Custom Weekly Orders",
            },
        )

        updated = tools.execute_tool(
            "update_visual",
            {
                "view_id": created["payload"]["view_id"],
                "sort_order": "desc",
            },
        )

        self.assertTrue(updated["success"], updated)
        self.assertEqual(
            updated["payload"]["view"]["title"],
            "Custom Weekly Orders",
        )

    def test_update_visual_normalizes_explicit_invalid_title(self):
        for requested_title in ("", "订单周趋势"):
            with self.subTest(requested_title=requested_title):
                created = tools.execute_tool(
                    "create_visual",
                    {
                        "chart_type": "line",
                        "x": "order_week",
                        "y": "order_count",
                        "title": "Custom Weekly Orders",
                    },
                )

                updated = tools.execute_tool(
                    "update_visual",
                    {
                        "view_id": created["payload"]["view_id"],
                        "title": requested_title,
                    },
                )

                self.assertTrue(updated["success"], updated)
                self.assertEqual(
                    updated["payload"]["view"]["title"],
                    "Weekly Orders",
                )


if __name__ == "__main__":
    unittest.main()
