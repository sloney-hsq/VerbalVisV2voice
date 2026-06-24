/**
 * Vega-Lite spec factory.
 * Generates specs from view metadata; data is injected separately via vega-embed.
 */

const CHART_WIDTH = 360;
const CHART_HEIGHT = 240;

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
      x: { field: "order_month", type: "ordinal", title: "Month", axis: { labelAngle: -45 } },
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
    mark: { type: "bar", tooltip: true },
    encoding: {
      x: { field: "review_score", type: "ordinal", title: "Review Score" },
      y: { field: "order_count", type: "quantitative", title: "Count" },
      color: {
        field: "review_score",
        type: "ordinal",
        scale: { scheme: "orangered" },
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
      spec.encoding.x = { field: x, type: "nominal", title: x, sort: "-y" };
      spec.encoding.y = { field: y, type: "quantitative", title: y };
      if (color) {
        spec.encoding.color = { field: color, type: "nominal" };
      }
      break;

    case "line":
      spec.mark = { type: "line", point: true, tooltip: true };
      spec.encoding.x = { field: x, type: "ordinal", title: x };
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
      spec.encoding.x = { field: x, type: "nominal" };
      spec.encoding.y = { field: y, type: "quantitative" };
  }

  return spec;
}
