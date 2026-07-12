import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  DEFAULT_CHART_HEIGHT,
  MAX_CHART_HEIGHT,
  chartHeightForView,
} from "../src/chartLayout.js";
import { createSpec } from "../src/specFactory.js";
import { compile } from "vega-lite";
import { reactive } from "vue";

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
  /grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(min\(100%,\s*400px\),\s*1fr\)\)/,
  "The workspace must use a fluid auto-fit chart grid.",
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
assert.doesNotMatch(
  chartSlot,
  /max-width:\s*540px/,
  "Chart cards must fill their responsive grid tracks.",
);
assert.match(chartSlot, /height:\s*clamp\(330px,\s*28vw,\s*360px\)/);
assert.match(chartSlot, /min-height:\s*330px/);
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
assert.match(specFactory, /view\.order_contract/);
assert.match(specFactory, /view\.focus_x/);
assert.match(specFactory, /COMPARISON_COLORS/);
assert.match(chartSlot, /Shared order/);
assert.match(chartSlot, /Focus/);
assert.match(chartSlot, /props\.view\.y_field === "low_score_ratio"/);
assert.match(chartSlot, /view\.low_score_threshold \?\? 2/);
assert.match(dashboard, /groupTranscriptItems/);
assert.match(dashboard, /conversationGroups/);
assert.match(dashboard, /timeline--collapsed/);
assert.match(dashboard, /Actions \(/);

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

const sharedCategories = ["watches_gifts", "bed_bath_table", "office_furniture"];
const categorySpec = createSpec({
  chart_type: "bar",
  x_field: "product_category",
  y_field: "low_score_ratio",
  order_contract: {
    field: "product_category",
    mode: "shared_rank",
    values: sharedCategories,
    verified: true,
  },
});
assert.deepEqual(
  categorySpec.encoding.y.sort,
  sharedCategories,
  "Task B bars must use the backend-verified shared revenue order.",
);
compile(categorySpec);

const weeklySpec = createSpec({
  chart_type: "line",
  x_field: "order_week",
  y_field: "order_count",
  color: "product_category",
  focus_x: "2017-W48",
  comparison_categories: ["watches_gifts", "bed_bath_table"],
  order_contract: {
    field: "order_week",
    mode: "time",
    values: ["2017-W47", "2017-W48", "2017-W49"],
    verified: true,
  },
});
assert.ok(Array.isArray(weeklySpec.layer));
assert.equal(weeklySpec.layer[0].encoding.x.datum, "2017-W48");
assert.deepEqual(
  weeklySpec.layer[1].encoding.x.sort,
  ["2017-W47", "2017-W48", "2017-W49"],
);
compile(weeklySpec);

const reactiveBaseView = reactive({
  chart_type: "line",
  x_field: "order_month",
  y_field: "order_count",
  order_contract: {
    field: "order_month",
    mode: "time",
    values: ["2017-01", "2017-02"],
    verified: true,
  },
  data: [
    { order_month: "2017-01", order_count: 10 },
    { order_month: "2017-02", order_count: 12 },
  ],
});
const reactiveSpec = createSpec(reactiveBaseView);
assert.equal(
  reactiveSpec.$schema,
  "https://vega.github.io/schema/vega-lite/v6.json",
);
assert.deepEqual(reactiveSpec.data?.values, [
  { order_month: "2017-01", order_count: 10 },
  { order_month: "2017-02", order_count: 12 },
]);
assert.doesNotThrow(
  () => structuredClone(reactiveSpec),
  "Vega specs must not retain Vue reactive proxies.",
);

console.log("Dashboard layout validation: PASS");
