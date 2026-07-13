import unittest

from backend.view_titles import MAX_VIEW_TITLE_LENGTH, short_view_title


class ViewTitleTests(unittest.TestCase):
    def test_preserves_short_english_title(self):
        title = short_view_title(
            "Monthly Orders Trend",
            chart_type="line",
            x="order_month",
            y="order_count",
        )
        self.assertEqual(title, "Monthly Orders Trend")

    def test_replaces_chinese_title_with_canonical_english_title(self):
        title = short_view_title(
            "RJ州Top 5营收品类运营指标周度趋势",
            chart_type="line",
            x="order_week",
            y="order_count",
            series="product_category",
            top_n=5,
            state="RJ",
        )
        self.assertEqual(title, "RJ Weekly Orders (Top 5)")

    def test_replaces_overlong_title_without_cutting_a_word(self):
        title = short_view_title(
            "Weekly low score ratio trend for the five highest revenue categories",
            chart_type="line",
            x="order_week",
            y="low_score_ratio",
            series="product_category",
            top_n=5,
        )
        self.assertEqual(title, "Weekly Low-score Share (Top 5)")
        self.assertLessEqual(len(title), MAX_VIEW_TITLE_LENGTH)

    def test_builds_normalized_bar_title(self):
        title = short_view_title(
            "各州评分占比",
            chart_type="bar",
            x="customer_state",
            y="order_count",
            series="review_score",
            normalize=True,
        )
        self.assertEqual(title, "Review Score Share by State")


if __name__ == "__main__":
    unittest.main()
