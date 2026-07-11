import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  DEFAULT_CHART_HEIGHT,
  MAX_CHART_HEIGHT,
  chartHeightForView,
} from "../src/chartLayout.js";

const here = dirname(fileURLToPath(import.meta.url));
const srcRoot = resolve(here, "../src");

const dashboard = readFileSync(
  resolve(srcRoot, "components/Dashboard.vue"),
  "utf8",
);
const chartSlot = readFileSync(
  resolve(srcRoot, "components/ChartSlot.vue"),
  "utf8",
);
const specFactory = readFileSync(resolve(srcRoot, "specFactory.js"), "utf8");

assert.match(
  dashboard,
  /grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/,
  "Wide screens must use four equal columns.",
);
assert.match(
  dashboard,
  /@media \(max-width: 1799px\)[\s\S]*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
  "Medium-wide screens must use three equal columns.",
);
assert.match(
  dashboard,
  /@media \(max-width: 1279px\)[\s\S]*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
  "Desktop screens must use two equal columns.",
);
assert.match(
  dashboard,
  /@media \(max-width: 899px\)[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
  "Small screens must use one column.",
);
assert.doesNotMatch(
  dashboard,
  /chart-card[^\n{]*[\s\S]{0,120}grid-column:\s*span/i,
  "No chart type may span extra grid columns.",
);

assert.match(specFactory, /width:\s*"container"/);
assert.match(specFactory, /autosize:\s*\{[\s\S]*type:\s*"fit"/);
assert.match(specFactory, /resize:\s*true/);
assert.doesNotMatch(
  specFactory,
  /title:\s*view\.title/,
  "The Vega spec must not duplicate the card title.",
);
assert.match(chartSlot, /min-height:\s*270px/);
assert.match(chartSlot, /chartHeightForView/);

assert.equal(
  chartHeightForView({ chart_type: "line", data: Array(30).fill({}) }),
  DEFAULT_CHART_HEIGHT,
  "Non-category views keep the compact default plotting height.",
);
assert.equal(
  chartHeightForView({
    chart_type: "bar",
    x_field: "product_category",
    data: Array(15).fill({}),
  }),
  292,
  "Top-15 category bars receive enough internal plotting height.",
);
assert.equal(
  chartHeightForView({
    chart_type: "bar",
    x_field: "product_category",
    data: Array(100).fill({}),
  }),
  MAX_CHART_HEIGHT,
  "Dense category bars remain capped at the maximum plotting height.",
);

console.log("Dashboard layout validation: PASS");
