import assert from "node:assert/strict";
import {
  applyHighlightToSpec,
  datumMatchesHighlight,
  resolveHighlight,
} from "../src/highlightSpec.js";

const weeklyView = {
  id: "view5",
  chart_type: "line",
  x_field: "order_week",
  y_field: "order_count",
  color: "product_category",
  data: [
    { order_week: "2017-W47", product_category: "office_furniture", order_count: 11 },
    { order_week: "2017-W48", product_category: "office_furniture", order_count: 18 },
    { order_week: "2017-W48", product_category: "bed_bath_table", order_count: 25 },
  ],
};

const baseLineSpec = {
  $schema: "https://vega.github.io/schema/vega-lite/v5.json",
  mark: { type: "line", point: true },
  encoding: {
    x: { field: "order_week", type: "ordinal" },
    y: { field: "order_count", type: "quantitative" },
    color: { field: "product_category", type: "nominal" },
    detail: { field: "product_category" },
  },
};

const weekHighlight = resolveHighlight(weeklyView, "2017-W48");
assert.equal(weekHighlight.matchedCount, 2);
assert.equal(weekHighlight.clauses[0].field, "order_week");
assert.equal(weekHighlight.clauses[0].value, "2017-W48");

const weekSpec = applyHighlightToSpec(baseLineSpec, weeklyView, "2017-W48");
assert.ok(Array.isArray(weekSpec.layer));
assert.ok(weekSpec.layer.some((layer) => layer.mark?.type === "rule"));
assert.ok(weekSpec.layer.some((layer) => layer.mark?.type === "point"));

const seriesHighlight = resolveHighlight(weeklyView, "office_furniture");
assert.equal(seriesHighlight.matchedCount, 2);
assert.equal(seriesHighlight.clauses[0].field, "product_category");

const pointHighlight = resolveHighlight(
  weeklyView,
  "order_week=2017-W48, product_category=office_furniture",
);
assert.equal(pointHighlight.matchedCount, 1);
assert.equal(pointHighlight.clauses.length, 2);
assert.equal(
  datumMatchesHighlight(weeklyView.data[1], pointHighlight),
  true,
);
assert.equal(
  datumMatchesHighlight(weeklyView.data[2], pointHighlight),
  false,
);

const categoryView = {
  id: "view9",
  chart_type: "bar",
  x_field: "product_category",
  y_field: "revenue",
  color: null,
  data: [
    { product_category: "office_furniture", revenue: 1000 },
    { product_category: "bed_bath_table", revenue: 1500 },
  ],
};
const barSpec = {
  mark: { type: "bar" },
  encoding: {
    y: { field: "product_category", type: "nominal" },
    x: { field: "revenue", type: "quantitative" },
  },
};
const highlightedBarSpec = applyHighlightToSpec(
  barSpec,
  categoryView,
  "office_furniture",
);
assert.equal(
  highlightedBarSpec.encoding.opacity.condition.value,
  1,
);
assert.equal(
  highlightedBarSpec.encoding.strokeWidth.condition.value,
  3,
);

const unmatched = resolveHighlight(categoryView, "not_a_real_category");
assert.equal(unmatched, null);
assert.deepEqual(
  applyHighlightToSpec(barSpec, categoryView, "not_a_real_category"),
  barSpec,
);

console.log("Highlight validation: PASS");
