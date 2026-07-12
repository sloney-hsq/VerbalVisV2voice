import assert from "node:assert/strict";
import { compile } from "vega-lite";
import { createSpec } from "../src/specFactory.js";

const view = {
  id: "view5",
  chart_type: "bar",
  x_field: "customer_state",
  y_field: "order_count",
  color: "review_score",
  normalize: true,
  normalized_field: "normalized_value",
  sort_by: "customer_state",
  sort_order: "asc",
  data: [],
};

const spec = createSpec(view);

assert.equal(spec.encoding.x.field, "customer_state");
assert.deepEqual(spec.encoding.x.sort, {
  field: "customer_state",
  order: "ascending",
});
assert.equal(spec.encoding.y.field, "normalized_value");
assert.equal(spec.encoding.y.stack, "zero");
assert.equal(spec.encoding.y.axis.format, ".0%");
assert.deepEqual(spec.encoding.color.scale.domain, ["null", "1", "2", "3", "4", "5"]);
assert.deepEqual(spec.encoding.color.legend.values, ["null", "1", "2", "3", "4", "5"]);
assert.equal(spec.encoding.order.field, "__review_score_order");
assert.equal(spec.encoding.order.sort, "ascending");
assert.ok(spec.transform.some((item) => item.as === "__review_score_label"));
assert.ok(spec.encoding.tooltip.some((item) => item.field === "normalized_value"));
assert.ok(spec.encoding.tooltip.some((item) => item.field === "order_count"));

const compiled = compile({
  ...spec,
  data: {
    values: [
      {
        customer_state: "SP",
        review_score: null,
        order_count: 2,
        normalized_value: 0.2,
      },
      {
        customer_state: "SP",
        review_score: 5,
        order_count: 8,
        normalized_value: 0.8,
      },
    ],
  },
}).spec;
assert.ok(compiled.marks?.length, "Vega-Lite must compile the normalized chart");

console.log("Normalized rating chart validation: PASS");
