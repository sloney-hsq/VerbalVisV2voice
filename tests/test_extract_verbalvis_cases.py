import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "extract_verbalvis_cases.py"


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def append_csv(path, fieldnames, rows):
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writerows(rows)


class ExtractVerbalVisCasesTest(unittest.TestCase):
    def make_olist_data(self, data_dir):
        write_csv(
            data_dir / "olist_orders_dataset.csv",
            [
                "order_id", "customer_id", "order_status",
                "order_purchase_timestamp", "order_delivered_customer_date",
                "order_estimated_delivery_date",
            ],
            [
                {"order_id": "sp47", "customer_id": "c_sp47", "order_status": "delivered", "order_purchase_timestamp": "2017-11-20 09:00:00", "order_delivered_customer_date": "2017-11-26 09:00:00", "order_estimated_delivery_date": "2017-11-28 09:00:00"},
                {"order_id": "sp48a", "customer_id": "c_sp48a", "order_status": "delivered", "order_purchase_timestamp": "2017-11-28 09:00:00", "order_delivered_customer_date": "2017-12-03 09:00:00", "order_estimated_delivery_date": "2017-12-01 09:00:00"},
                {"order_id": "sp48b", "customer_id": "c_sp48b", "order_status": "delivered", "order_purchase_timestamp": "2017-11-29 09:00:00", "order_delivered_customer_date": "2017-12-03 09:00:00", "order_estimated_delivery_date": "2017-12-05 09:00:00"},
                {"order_id": "sp_other", "customer_id": "c_sp_other", "order_status": "delivered", "order_purchase_timestamp": "2017-12-02 09:00:00", "order_delivered_customer_date": "2017-12-04 09:00:00", "order_estimated_delivery_date": "2017-12-06 09:00:00"},
                {"order_id": "sp_no_w48", "customer_id": "c_sp_no_w48", "order_status": "delivered", "order_purchase_timestamp": "2017-11-20 12:00:00", "order_delivered_customer_date": "2017-11-22 12:00:00", "order_estimated_delivery_date": "2017-11-25 12:00:00"},
                {"order_id": "sp_no_w48_tie", "customer_id": "c_sp_no_w48_tie", "order_status": "delivered", "order_purchase_timestamp": "2017-11-13 12:00:00", "order_delivered_customer_date": "2017-11-15 12:00:00", "order_estimated_delivery_date": "2017-11-18 12:00:00"},
                {"order_id": "rj_office_low", "customer_id": "c_rj_office_low", "order_status": "delivered", "order_purchase_timestamp": "2017-12-01 09:00:00", "order_delivered_customer_date": "2017-12-05 09:00:00", "order_estimated_delivery_date": "2017-12-03 09:00:00"},
                {"order_id": "rj_office_high", "customer_id": "c_rj_office_high", "order_status": "delivered", "order_purchase_timestamp": "2018-01-01 09:00:00", "order_delivered_customer_date": "2018-01-03 09:00:00", "order_estimated_delivery_date": "2018-01-04 09:00:00"},
                {"order_id": "rj_other", "customer_id": "c_rj_other", "order_status": "delivered", "order_purchase_timestamp": "2018-02-01 09:00:00", "order_delivered_customer_date": "2018-02-02 09:00:00", "order_estimated_delivery_date": "2018-02-04 09:00:00"},
            ],
        )
        write_csv(
            data_dir / "olist_customers_dataset.csv",
            ["customer_id", "customer_state"],
            [
                *[{"customer_id": f"c_{suffix}", "customer_state": "SP"} for suffix in ("sp47", "sp48a", "sp48b", "sp_other", "sp_no_w48", "sp_no_w48_tie")],
                *[{"customer_id": f"c_{suffix}", "customer_state": "RJ"} for suffix in ("rj_office_low", "rj_office_high", "rj_other")],
            ],
        )
        write_csv(
            data_dir / "olist_order_items_dataset.csv",
            ["order_id", "order_item_id", "product_id", "price"],
            [
                {"order_id": "sp47", "order_item_id": "1", "product_id": "office", "price": "100"},
                {"order_id": "sp48a", "order_item_id": "1", "product_id": "office", "price": "30"},
                {"order_id": "sp48a", "order_item_id": "2", "product_id": "office", "price": "50"},
                {"order_id": "sp48b", "order_item_id": "1", "product_id": "office", "price": "20"},
                {"order_id": "sp_other", "order_item_id": "1", "product_id": "other", "price": "210"},
                {"order_id": "sp_no_w48", "order_item_id": "1", "product_id": "no_w48", "price": "150"},
                {"order_id": "sp_no_w48_tie", "order_item_id": "1", "product_id": "no_w48", "price": "10"},
                {"order_id": "rj_office_low", "order_item_id": "1", "product_id": "office", "price": "100"},
                {"order_id": "rj_office_high", "order_item_id": "1", "product_id": "office", "price": "100"},
                {"order_id": "rj_other", "order_item_id": "1", "product_id": "other", "price": "300"},
            ],
        )
        write_csv(
            data_dir / "olist_products_dataset.csv",
            ["product_id", "product_category_name"],
            [
                {"product_id": "office", "product_category_name": "moveis_escritorio"},
                {"product_id": "other", "product_category_name": "categoria_outros"},
                {"product_id": "no_w48", "product_category_name": "categoria_sem_w48"},
            ],
        )
        write_csv(
            data_dir / "product_category_name_translation.csv",
            ["product_category_name", "product_category_name_english"],
            [
                {"product_category_name": "moveis_escritorio", "product_category_name_english": "office_furniture"},
                {"product_category_name": "categoria_outros", "product_category_name_english": "other_category"},
                {"product_category_name": "categoria_sem_w48", "product_category_name_english": "no_week48_category"},
            ],
        )
        write_csv(
            data_dir / "olist_order_reviews_dataset.csv",
            ["review_id", "order_id", "review_score"],
            [
                {"review_id": "r1", "order_id": "sp47", "review_score": "5"},
                {"review_id": "r2", "order_id": "sp48a", "review_score": "1"},
                {"review_id": "r3", "order_id": "sp48b", "review_score": "5"},
                {"review_id": "r4", "order_id": "sp_other", "review_score": "5"},
                {"review_id": "r4b", "order_id": "sp_no_w48", "review_score": "5"},
                {"review_id": "r4c", "order_id": "sp_no_w48_tie", "review_score": "5"},
                {"review_id": "r5", "order_id": "rj_office_low", "review_score": "1"},
                {"review_id": "r6", "order_id": "rj_office_high", "review_score": "5"},
                {"review_id": "r7", "order_id": "rj_other", "review_score": "5"},
            ],
        )

    def test_exports_case_metrics_without_item_level_double_counting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            output_dir = Path(temp_dir) / "output"
            data_dir.mkdir()
            self.make_olist_data(data_dir)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--data-dir", str(data_dir), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            expected_files = {
                "case1_sp_top5_categories.csv",
                "case1_sp_weekly_metrics.csv",
                "case1_sp_peak_weeks.csv",
                "case1_sp_week48_comparison.csv",
                "case2_rj_top15_metrics.csv",
                "case2_office_furniture_comparison.csv",
                "case2_candidate_ranking.csv",
            }
            self.assertEqual({path.name for path in output_dir.iterdir()}, expected_files)

            top5 = read_csv(output_dir / "case1_sp_top5_categories.csv")
            office = next(row for row in top5 if row["product_category"] == "office_furniture")
            self.assertEqual(office["total_revenue"], "200.00")
            self.assertEqual(office["order_count"], "3")

            weekly = read_csv(output_dir / "case1_sp_weekly_metrics.csv")
            week48 = next(
                row for row in weekly
                if row["product_category"] == "office_furniture" and row["iso_year"] == "2017" and row["iso_week"] == "48"
            )
            self.assertEqual(week48["order_count"], "2")
            self.assertEqual(week48["low_score_order_count"], "1")
            self.assertEqual(week48["scored_order_count"], "2")
            self.assertEqual(week48["low_score_ratio"], "0.500000")
            self.assertEqual(week48["avg_delivery_days"], "4.500000")
            self.assertEqual(week48["valid_delivery_order_count"], "2")
            self.assertEqual(week48["late_order_count"], "1")
            self.assertEqual(week48["lateness_eligible_order_count"], "2")
            self.assertEqual(week48["late_order_ratio"], "0.500000")

            no_week48 = next(
                row for row in weekly
                if row["product_category"] == "no_week48_category" and row["iso_year"] == "2017" and row["iso_week"] == "48"
            )
            self.assertEqual(no_week48["order_count"], "0")
            self.assertEqual(no_week48["low_score_order_count"], "0")
            self.assertEqual(no_week48["low_score_ratio"], "")
            self.assertEqual(no_week48["avg_delivery_days"], "")
            self.assertEqual(no_week48["late_order_ratio"], "")

            peak_weeks = read_csv(output_dir / "case1_sp_peak_weeks.csv")
            tied_peak = next(
                row for row in peak_weeks
                if row["product_category"] == "no_week48_category" and row["metric"] == "order_count"
            )
            self.assertEqual(tied_peak["peak_week_count"], "2")
            self.assertEqual(tied_peak["peak_iso_weeks"], "2017-W46|2017-W47")

            comparison = read_csv(output_dir / "case1_sp_week48_comparison.csv")
            delivery = next(
                row for row in comparison
                if row["product_category"] == "office_furniture" and row["metric"] == "avg_delivery_days"
            )
            self.assertEqual(delivery["week48_value"], "4.500000")
            self.assertEqual(delivery["week48_rank"], "2")
            self.assertEqual(delivery["peak_iso_week"], "2017-W47")
            self.assertEqual(delivery["peak_value"], "6.000000")
            self.assertEqual(delivery["week48_minus_peak"], "-1.500000")

            rj_metrics = read_csv(output_dir / "case2_rj_top15_metrics.csv")
            rj_office = next(row for row in rj_metrics if row["product_category"] == "office_furniture")
            self.assertEqual(rj_office["total_revenue"], "200.00")
            self.assertEqual(rj_office["order_count"], "2")
            self.assertEqual(rj_office["low_score_ratio"], "0.500000")
            self.assertEqual(rj_office["avg_delivery_days"], "3.000000")
            self.assertEqual(rj_office["late_order_ratio"], "0.500000")
            self.assertEqual(rj_office["avg_product_revenue_per_order"], "100.000000")

            office_comparison = read_csv(output_dir / "case2_office_furniture_comparison.csv")
            other = next(row for row in office_comparison if row["product_category"] == "other_category")
            self.assertEqual(other["office_furniture_present_in_rj_data"], "true")
            self.assertEqual(other["revenue_difference_vs_office_furniture"], "100.00")
            self.assertEqual(other["order_count_difference_vs_office_furniture"], "-1")
            self.assertEqual(other["low_score_ratio_difference_vs_office_furniture"], "-0.500000")
            self.assertEqual(other["avg_delivery_days_difference_vs_office_furniture"], "-2.000000")
            self.assertEqual(other["late_order_ratio_difference_vs_office_furniture"], "-0.500000")
            self.assertEqual(other["avg_product_revenue_per_order_difference_vs_office_furniture"], "200.000000")

    def test_compares_top15_categories_to_office_furniture_even_when_office_is_not_top15(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            output_dir = Path(temp_dir) / "output"
            data_dir.mkdir()
            self.make_olist_data(data_dir)

            extra_orders = []
            extra_customers = []
            extra_items = []
            extra_products = []
            extra_translations = []
            extra_reviews = []
            for index in range(15):
                order_id = f"rj_large_{index}"
                customer_id = f"c_{order_id}"
                product_id = f"large_{index}"
                source_category = f"categoria_grande_{index}"
                extra_orders.append({"order_id": order_id, "customer_id": customer_id, "order_status": "delivered", "order_purchase_timestamp": "2018-03-01 09:00:00", "order_delivered_customer_date": "2018-03-02 09:00:00", "order_estimated_delivery_date": "2018-03-03 09:00:00"})
                extra_customers.append({"customer_id": customer_id, "customer_state": "RJ"})
                extra_items.append({"order_id": order_id, "order_item_id": "1", "product_id": product_id, "price": "1000"})
                extra_products.append({"product_id": product_id, "product_category_name": source_category})
                extra_translations.append({"product_category_name": source_category, "product_category_name_english": f"large_category_{index}"})
                extra_reviews.append({"review_id": f"large_review_{index}", "order_id": order_id, "review_score": "5"})
            append_csv(data_dir / "olist_orders_dataset.csv", ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"], extra_orders)
            append_csv(data_dir / "olist_customers_dataset.csv", ["customer_id", "customer_state"], extra_customers)
            append_csv(data_dir / "olist_order_items_dataset.csv", ["order_id", "order_item_id", "product_id", "price"], extra_items)
            append_csv(data_dir / "olist_products_dataset.csv", ["product_id", "product_category_name"], extra_products)
            append_csv(data_dir / "product_category_name_translation.csv", ["product_category_name", "product_category_name_english"], extra_translations)
            append_csv(data_dir / "olist_order_reviews_dataset.csv", ["review_id", "order_id", "review_score"], extra_reviews)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--data-dir", str(data_dir), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            metrics = read_csv(output_dir / "case2_rj_top15_metrics.csv")
            self.assertNotIn("office_furniture", {row["product_category"] for row in metrics})
            comparison = read_csv(output_dir / "case2_office_furniture_comparison.csv")
            top_category = next(row for row in comparison if row["product_category"] == "large_category_0")
            self.assertEqual(top_category["office_furniture_in_top15"], "false")
            self.assertEqual(top_category["office_furniture_present_in_rj_data"], "true")
            self.assertEqual(top_category["revenue_difference_vs_office_furniture"], "800.00")


if __name__ == "__main__":
    unittest.main()
