/**
 * Vega-Lite spec factory.
 * Generates specs from view metadata; data is injected separately via vega-embed.
 */

const CHART_WIDTH = 360;
const CHART_HEIGHT = 240;
const TIME_FIELDS = new Set(["order_month", "order_week", "order_date", "order_dow", "order_hour"]);

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
      return dynamicSpec(chart_type, x_field, y_field, color, title);
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

function dynamicSpec(chart_type, x, y, color, title) {
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
      spec.encoding.x = xEncoding(x, x, { sort: isTimeField(x) ? "ascending" : "-y" });
      spec.encoding.y = { field: y, type: "quantitative", title: y };
      if (color) {
        spec.encoding.color = { field: color, type: "nominal" };
      }
      break;

    case "line":
      spec.mark = { type: "line", point: true, tooltip: true };
      spec.encoding.x = xEncoding(x, x, { sort: "ascending" });
      spec.encoding.y = { field: y, type: "quantitative", title: y };
      if (color) {
        spec.encoding.color = { field: color, type: "nominal" };
      }
      break;

    case "histogram":
      spec.mark = { type: "bar", tooltip: true };
      spec.encoding.x = { field: x, type: "quantitative", bin: true, title: x };
      spec.encoding.y = { aggregate: "count", type: "quantitative", title: "Count" };
      break;

    default:
      spec.mark = { type: "bar", tooltip: true };
      spec.encoding.x = xEncoding(x, x, { sort: isTimeField(x) ? "ascending" : undefined });
      spec.encoding.y = { field: y, type: "quantitative" };
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

function stripUndefined(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, value]) => value !== undefined));
}
