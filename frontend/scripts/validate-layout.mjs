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
const dashboardStore = readFileSync(
  resolve(srcRoot, "stores/dashboard.js"),
  "utf8",
);

assert.match(
  dashboard,
  /grid-template-columns:\s*repeat\(auto-fill,\s*540px\)/,
  "Desktop grids must use fixed 540 px view columns.",
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
assert.match(chartSlot, /max-width:\s*540px/);
assert.match(chartSlot, /height:\s*360px/);
assert.match(chartSlot, /min-height:\s*360px/);
assert.doesNotMatch(chartSlot, /aspect-ratio:\s*1\s*\/\s*1/);
assert.match(chartSlot, /chartHeightForView/);
assert.match(chartSlot, /import\("vega-embed"\)/);
assert.doesNotMatch(chartSlot, /^import vegaEmbed from "vega-embed"/m);
assert.match(
  dashboardStore,
  /item\.error\s*=\s*result\.success\s*===\s*false/,
  "Failed tools must retain their concrete error in the transcript.",
);
assert.match(
  dashboardStore,
  /if \(item\.error\) item\.expanded = true/,
  "Failed tools must expand automatically so users can see why scope changes failed.",
);
assert.match(dashboard, /class="tool-error"/);
assert.match(dashboard, />All data<\/span>/);
assert.match(dashboard, /ws\.runtime\.lastToolError/);
assert.match(specFactory, /view\.comparison_categories/);
assert.match(specFactory, /COMPARISON_COLORS/);
assert.match(chartSlot, /props\.view\.y_field === "low_score_ratio"/);
assert.match(chartSlot, /view\.low_score_threshold \?\? 2/);

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
  287,
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
