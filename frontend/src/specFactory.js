/**
 * Vega-Lite spec factory.
 * Generates specs from view metadata; data is injected separately via vega-embed.
 */

const CHART_WIDTH = 360;
const CHART_HEIGHT = 240;
const TIME_FIELDS = new Set(["order_month", "order_week", "order_date", "order_dow", "order_hour"]);
const RATIO_FIELDS = new Set(["low_score_ratio"]);

export function createSpec(view) {
  const { id, chart_type, title, x_field, y_field, color } = view;

  switch (id) {
    case "view-trend":
      return trendSpec(title);
    case "view-review":
      return reviewSpec(title);
    case "view-map":
      return mapBarSpec(title);
    case "view-category":
      return categorySpec(title);
    default:
      return dynamicSpec(chart_type, x_field, y_field, color, title, view);
  }
}

// ------------------------------------------------------------------
// Base view specs
// ------------------------------------------------------------------

function trendSpec(title) {
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    title,
    width: CHART_WIDTH,
    height: CHART_HEIGHT,
    mark: { type: "line", point: true, tooltip: true },
    encoding: {
      x: timeXEncoding("order_month", "Month", { axis: { labelAngle: -45 } }),
      y: { field: "order_count", type: "quantitative", title: "Orders" },
    },
  };
}

function reviewSpec(title) {
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    title,
    width: CHART_WIDTH,
    height: CHART_HEIGHT,
    mark: { type: "bar", tooltip: true, cornerRadiusEnd: 3 },
    encoding: {
      x: { field: "review_score", type: "ordinal", title: "Review Score" },
      y: { field: "order_count", type: "quantitative", title: "Count" },
      color: {
        field: "review_score",
        type: "ordinal",
        scale: {
          range: ["#dbeafe", "#bfdbfe", "#93c5fd", "#2563eb", "#0f2f66"],
        },
        legend: null,
      },
    },
  };
}

function mapBarSpec(title) {
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    title,
    width: CHART_WIDTH,
    height: CHART_HEIGHT,
    mark: { type: "bar", tooltip: true },
    encoding: {
      x: { field: "customer_state", type: "nominal", title: "State", sort: "-y" },
      y: { field: "order_count", type: "quantitative", title: "Orders" },
    },
  };
}

function categorySpec(title) {
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    title,
    width: CHART_WIDTH,
    height: CHART_HEIGHT,
    mark: { type: "bar", tooltip: true },
    encoding: {
      y: { field: "product_category", type: "nominal", title: "Category", sort: "-x" },
      x: { field: "revenue", type: "quantitative", title: "Revenue (R$)" },
    },
  };
}

// ------------------------------------------------------------------
// Dynamic specs for workspace views
// ------------------------------------------------------------------

function dynamicSpec(chart_type, x, y, color, title, view = {}) {
  const spec = {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    title,
    width: CHART_WIDTH,
    height: CHART_HEIGHT,
    encoding: {},
  };

  switch (chart_type) {
    case "scatter":
      spec.mark = { type: "circle", tooltip: true, opacity: 0.6 };
      spec.encoding.x = { field: x, type: "quantitative", title: x };
      spec.encoding.y = { field: y, type: "quantitative", title: y };
      if (color) {
        spec.encoding.color = { field: color, type: "nominal" };
      }
      break;

    case "bar":
      spec.mark = { type: "bar", tooltip: true };
      if (x === "product_category") {
        spec.encoding.y = {
          field: x,
          type: "nominal",
          title: fieldTitle(x),
          sort: sortEncoding(view, "-x"),
        };
        spec.encoding.x = quantitativeEncoding(y);
      } else {
        spec.encoding.x = xEncoding(x, fieldTitle(x), {
          sort: isTimeField(x) ? "ascending" : sortEncoding(view, "-y"),
        });
        spec.encoding.y = quantitativeEncoding(y);
      }
      if (color) {
        spec.encoding.color = { field: color, type: "nominal" };
      }
      addRatioTooltip(spec, x, y);
      break;

    case "line":
      spec.mark = { type: "line", point: true, tooltip: true };
      spec.encoding.x = xEncoding(x, fieldTitle(x), { sort: "ascending" });
      spec.encoding.y = quantitativeEncoding(y);
      if (color) {
        spec.encoding.color = { field: color, type: "nominal" };
      }
      addRatioTooltip(spec, x, y);
      break;

    case "histogram":
      spec.mark = { type: "bar", tooltip: true };
      spec.encoding.x = { field: x, type: "quantitative", bin: true, title: fieldTitle(x) };
      spec.encoding.y = { aggregate: "count", type: "quantitative", title: "Count" };
      break;

    case "pie":
      spec.transform = [
        { joinaggregate: [{ op: "sum", field: y, as: "__total" }] },
        { calculate: `datum["${y}"] / datum.__total`, as: "__share" },
      ];
      spec.mark = { type: "arc", tooltip: true, outerRadius: 108, innerRadius: 0 };
      spec.encoding.theta = { field: y, type: "quantitative", stack: true, title: fieldTitle(y) };
      spec.encoding.color = {
        field: x,
        type: "nominal",
        title: fieldTitle(x),
        legend: { orient: "right", labelLimit: 140, titleLimit: 140 },
      };
      spec.encoding.order = view?.sort_by
        ? { field: "rank", type: "quantitative", sort: "ascending" }
        : { field: y, type: "quantitative", sort: "descending" };
      spec.encoding.tooltip = [
        { field: x, type: "nominal", title: fieldTitle(x) },
        { field: y, type: "quantitative", title: fieldTitle(y), format: isRatioField(y) ? ".1%" : "," },
        { field: "__share", type: "quantitative", title: "Share", format: ".1%" },
      ];
      break;

    default:
      spec.mark = { type: "bar", tooltip: true };
      spec.encoding.x = xEncoding(x, fieldTitle(x), { sort: isTimeField(x) ? "ascending" : undefined });
      spec.encoding.y = quantitativeEncoding(y);
  }

  return spec;
}

function isTimeField(field) {
  return TIME_FIELDS.has(field);
}

function xEncoding(field, title, extra = {}) {
  if (isTimeField(field)) {
    return timeXEncoding(field, title, extra);
  }
  return stripUndefined({
    field,
    type: "nominal",
    title,
    ...extra,
  });
}

function sortEncoding(view, fallback) {
  if (view?.sort_by && !isTimeField(view.x_field)) {
    return { field: "rank", order: "ascending" };
  }
  return fallback;
}

function quantitativeEncoding(field) {
  return stripUndefined({
    field,
    type: "quantitative",
    title: fieldTitle(field),
    axis: isRatioField(field) ? { format: ".0%" } : undefined,
  });
}

function timeXEncoding(field, title, extra = {}) {
  return stripUndefined({
    field,
    type: field === "order_date" ? "temporal" : "ordinal",
    title,
    sort: "ascending",
    axis: field === "order_date" ? { labelAngle: -45 } : undefined,
    ...extra,
  });
}

function fieldTitle(field) {
  const titles = {
    order_month: "Month",
    order_week: "Week",
    order_date: "Date",
    order_dow: "Day of Week",
    order_hour: "Hour",
    review_score: "Review Score",
    customer_state: "State",
    product_category: "Category",
    delivery_days: "Delivery Days",
    delivery_speed_bucket: "Delivery Speed",
    revenue: "Revenue (R$)",
    order_count: "Orders",
    low_score_ratio: "Low-score Ratio",
  };
  return titles[field] || field;
}

function isRatioField(field) {
  return RATIO_FIELDS.has(field);
}

function addRatioTooltip(spec, x, y) {
  if (!isRatioField(y)) return;
  spec.encoding.tooltip = [
    { field: x, title: fieldTitle(x) },
    { field: y, type: "quantitative", title: fieldTitle(y), format: ".1%" },
    { field: "low_score_count", type: "quantitative", title: "Low-score Orders" },
    { field: "order_count", type: "quantitative", title: "Orders" },
  ];
}

function stripUndefined(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, value]) => value !== undefined));
}
