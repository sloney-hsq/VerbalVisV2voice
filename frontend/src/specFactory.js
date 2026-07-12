import { applyHighlightToSpec } from "./highlightSpec.js";
import { chartHeightForView } from "./chartLayout.js";

const TIME_FIELDS = new Set(["order_month", "order_week", "order_date"]);
const DIMENSION_FIELDS = new Set([
  "order_month",
  "order_week",
  "order_date",
  "customer_state",
  "product_category",
  "review_score",
]);
const RATIO_FIELDS = new Set(["low_score_ratio", "late_ratio"]);
const COMPARISON_COLORS = [
  "#2563eb",
  "#dc2626",
  "#059669",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#65a30d",
  "#9333ea",
  "#475569",
];
const REVIEW_SCORE_DOMAIN = ["null", "1", "2", "3", "4", "5"];
const REVIEW_SCORE_COLORS = [
  "#94a3b8",
  "#b91c1c",
  "#ea580c",
  "#eab308",
  "#65a30d",
  "#15803d",
];

/** Build one responsive Vega-Lite specification from backend view metadata. */
export function createSpec(view, highlightElement = null) {
  const spec = {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    width: "container",
    height: chartHeightForView(view),
    autosize: {
      type: "fit",
      contains: "padding",
      resize: true,
    },
    encoding: {},
  };
  if (view.color === "review_score") {
    spec.transform = [
      {
        calculate: "isValid(datum.review_score) ? toString(datum.review_score) : 'null'",
        as: "__review_score_label",
      },
      {
        calculate: "isValid(datum.review_score) ? +datum.review_score : 0",
        as: "__review_score_order",
      },
    ];
  }

  if (view.chart_type === "scatter") buildScatter(spec, view);
  else if (view.chart_type === "line") buildLine(spec, view);
  else buildBar(spec, view);

  return applyHighlightToSpec(spec, view, highlightElement);
}

function buildLine(spec, view) {
  spec.mark = { type: "line", point: true, tooltip: true };
  spec.encoding.x = dimensionEncoding(view.x_field, { sort: "ascending" });
  spec.encoding.y = metricEncoding(view.y_field);
  if (view.color) {
    spec.encoding.color = seriesEncoding(view);
    spec.encoding.detail = { field: seriesField(view) };
  }
  spec.encoding.tooltip = tooltipFields(view);
}

function buildBar(spec, view) {
  const normalized = Boolean(view.normalize);
  spec.mark = {
    type: "bar",
    tooltip: true,
    cornerRadiusEnd: normalized ? 0 : 2,
  };
  if (view.x_field === "product_category") {
    spec.encoding.y = {
      field: view.x_field,
      type: "nominal",
      title: fieldTitle(view.x_field),
      sort: view.sort_by
        ? { field: view.sort_by, order: vegaOrder(view.sort_order) }
        : "-x",
    };
    spec.encoding.x = normalized
      ? normalizedMetricEncoding(view)
      : metricEncoding(view.y_field);
  } else {
    spec.encoding.x = dimensionEncoding(view.x_field, {
      sort: TIME_FIELDS.has(view.x_field)
        ? "ascending"
        : view.sort_by
          ? { field: view.sort_by, order: vegaOrder(view.sort_order) }
          : "-y",
    });
    spec.encoding.y = normalized
      ? normalizedMetricEncoding(view)
      : metricEncoding(view.y_field);
  }
  if (view.color) {
    spec.encoding.color = seriesEncoding(view);
  }
  if (normalized && view.color === "review_score") {
    spec.encoding.order = {
      field: "__review_score_order",
      type: "quantitative",
      sort: "ascending",
    };
  }
  spec.encoding.tooltip = tooltipFields(view);
}

function buildScatter(spec, view) {
  spec.mark = { type: "circle", tooltip: true, opacity: 0.62 };
  spec.encoding.x = metricEncoding(view.x_field);
  spec.encoding.y = metricEncoding(view.y_field);
  if (view.color) {
    spec.encoding.color = seriesEncoding(view);
  }
  spec.encoding.tooltip = tooltipFields(view);
}

function dimensionEncoding(field, extra = {}) {
  return compact({
    field,
    type: field === "order_date" ? "temporal" : "ordinal",
    title: fieldTitle(field),
    axis: field === "order_date" ? { labelAngle: -45 } : undefined,
    ...extra,
  });
}

function metricEncoding(field) {
  return compact({
    field,
    type: "quantitative",
    title: fieldTitle(field),
    axis: RATIO_FIELDS.has(field) ? { format: ".0%" } : undefined,
  });
}

function normalizedMetricEncoding(view) {
  return {
    field: view.normalized_field || "normalized_value",
    type: "quantitative",
    title: "Share",
    stack: "zero",
    scale: { domain: [0, 1] },
    axis: { format: ".0%" },
  };
}

function seriesEncoding(view) {
  if (view.color === "review_score") {
    return {
      field: "__review_score_label",
      type: "nominal",
      title: fieldTitle(view.color),
      sort: REVIEW_SCORE_DOMAIN,
      scale: {
        domain: REVIEW_SCORE_DOMAIN,
        range: REVIEW_SCORE_COLORS,
      },
      legend: { values: REVIEW_SCORE_DOMAIN },
    };
  }
  const domain = Array.isArray(view.comparison_categories)
    ? view.comparison_categories.filter(Boolean)
    : [];
  return compact({
    field: view.color,
    type: "nominal",
    title: fieldTitle(view.color),
    sort: domain.length ? domain : undefined,
    scale: domain.length
      ? {
          domain,
          range: domain.map((_, index) => (
            COMPARISON_COLORS[index % COMPARISON_COLORS.length]
          )),
        }
      : undefined,
  });
}

function tooltipFields(view) {
  const xType = view.chart_type === "scatter"
    ? "quantitative"
    : view.x_field === "order_date"
      ? "temporal"
      : DIMENSION_FIELDS.has(view.x_field)
        ? "nominal"
        : "quantitative";
  const fields = [
    {
      field: view.x_field,
      type: xType,
      title: fieldTitle(view.x_field),
    },
  ];
  if (view.color && view.color !== view.x_field) {
    fields.push({
      field: seriesField(view),
      type: "nominal",
      title: fieldTitle(view.color),
    });
  }
  if (view.normalize) {
    fields.push({
      field: view.normalized_field || "normalized_value",
      type: "quantitative",
      title: "Share",
      format: ".1%",
    });
  }
  if (view.y_field !== view.x_field) {
    fields.push(compact({
      field: view.y_field,
      type: "quantitative",
      title: fieldTitle(view.y_field),
      format: RATIO_FIELDS.has(view.y_field) ? ".1%" : undefined,
    }));
  }
  return fields;
}

function seriesField(view) {
  return view.color === "review_score"
    ? "__review_score_label"
    : view.color;
}

function vegaOrder(order) {
  return order === "asc" || order === "ascending" ? "ascending" : "descending";
}

function fieldTitle(field) {
  const titles = {
    order_month: "Month",
    order_week: "Week",
    order_date: "Date",
    customer_state: "State",
    product_category: "Category",
    order_count: "Orders",
    product_revenue: "Product revenue (R$)",
    low_score_ratio: "Low-score share",
    delivery_days: "Delivery days",
    late_ratio: "Late share",
    review_score: "Review score",
  };
  return titles[field] || field;
}

function compact(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined),
  );
}
