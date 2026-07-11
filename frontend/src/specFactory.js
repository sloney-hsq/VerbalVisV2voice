import { applyHighlightToSpec } from "./highlightSpec";

const CHART_WIDTH = 360;
const CHART_HEIGHT = 240;
const TIME_FIELDS = new Set(["order_month", "order_week", "order_date"]);
const RATIO_FIELDS = new Set(["low_score_ratio", "late_ratio"]);

/** Build one Vega-Lite specification from backend view metadata. */
export function createSpec(view, highlightElement = null) {
  const spec = {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    title: view.title,
    width: CHART_WIDTH,
    height: CHART_HEIGHT,
    encoding: {},
  };

  if (view.chart_type === "scatter") {
    buildScatter(spec, view);
  } else if (view.chart_type === "line") {
    buildLine(spec, view);
  } else {
    buildBar(spec, view);
  }

  return applyHighlightToSpec(spec, view, highlightElement);
}

function buildLine(spec, view) {
  spec.mark = { type: "line", point: true, tooltip: true };
  spec.encoding.x = dimensionEncoding(view.x_field, { sort: "ascending" });
  spec.encoding.y = metricEncoding(view.y_field);
  if (view.color) {
    spec.encoding.color = {
      field: view.color,
      type: "nominal",
      title: fieldTitle(view.color),
    };
    spec.encoding.detail = { field: view.color };
  }
  spec.encoding.tooltip = tooltipFields(view);
}

function buildBar(spec, view) {
  spec.mark = { type: "bar", tooltip: true, cornerRadiusEnd: 2 };
  if (view.x_field === "product_category") {
    spec.encoding.y = {
      field: view.x_field,
      type: "nominal",
      title: fieldTitle(view.x_field),
      sort: view.sort_by ? { field: view.y_field, order: view.sort_order || "descending" } : "-x",
    };
    spec.encoding.x = metricEncoding(view.y_field);
  } else {
    spec.encoding.x = dimensionEncoding(view.x_field, {
      sort: TIME_FIELDS.has(view.x_field)
        ? "ascending"
        : view.sort_by
          ? { field: view.y_field, order: view.sort_order || "descending" }
          : "-y",
    });
    spec.encoding.y = metricEncoding(view.y_field);
  }
  if (view.color) {
    spec.encoding.color = {
      field: view.color,
      type: "nominal",
      title: fieldTitle(view.color),
    };
  }
  spec.encoding.tooltip = tooltipFields(view);
}

function buildScatter(spec, view) {
  spec.mark = { type: "circle", tooltip: true, opacity: 0.62 };
  spec.encoding.x = metricEncoding(view.x_field);
  spec.encoding.y = metricEncoding(view.y_field);
  if (view.color) {
    spec.encoding.color = {
      field: view.color,
      type: "nominal",
      title: fieldTitle(view.color),
    };
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

function tooltipFields(view) {
  const fields = [
    {
      field: view.x_field,
      type: TIME_FIELDS.has(view.x_field) || view.x_field === "review_score"
        ? "ordinal"
        : "quantitative",
      title: fieldTitle(view.x_field),
    },
  ];
  if (view.color && view.color !== view.x_field) {
    fields.push({
      field: view.color,
      type: "nominal",
      title: fieldTitle(view.color),
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
