import { applyHighlightToSpec } from "./highlightSpec";

/**
 * Vega-Lite spec factory.
 * Generates specs from view metadata; data is injected separately via vega-embed.
 */

const CHART_WIDTH = 360;
const CHART_HEIGHT = 240;
const TIME_FIELDS = new Set(["order_month", "order_week", "order_date", "order_dow", "order_hour"]);
const RATIO_FIELDS = new Set([
  "low_score_ratio",
  "late_ratio",
  "on_time_ratio",
  "high_score_ratio",
  "avg_freight_ratio",
]);
const RATIO_COUNT_FIELDS = {
  low_score_ratio: { field: "low_score_count", title: "Low-score orders" },
  late_ratio: { field: "late_count", title: "Late orders" },
  on_time_ratio: { field: "on_time_count", title: "On-time orders" },
  high_score_ratio: { field: "high_score_count", title: "High-score orders" },
};

export function createSpec(view, highlightElement = null) {
  const { id, chart_type, title, x_field, y_field, color } = view;
  let spec;

  switch (id) {
    case "view1":
      spec = trendSpec(title);
      break;
    case "view2":
      spec = reviewSpec(title);
      break;
    case "view3":
      spec = mapBarSpec(title);
      break;
    case "view4":
      spec = categorySpec(title);
      break;
    default:
      spec = dynamicSpec(chart_type, x_field, y_field, color, title, view);
      break;
  }

  return applyHighlightToSpec(spec, view, highlightElement);
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
      x: { field: "review_score", type: "ordinal", title: "Review score" },
      y: { field: "order_count", type: "quantitative", title: "Orders" },
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
// Dynamic specs for user-created views
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
      spec.encoding.x = { field: x, type: "quantitative", title: fieldTitle(x) };
      spec.encoding.y = { field: y, type: "quantitative", title: fieldTitle(y) };
      if (color) {
        spec.encoding.color = { field: color, type: "nominal", title: fieldTitle(color) };
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
        spec.encoding.color = { field: color, type: "nominal", title: fieldTitle(color) };
      }
      addRatioTooltip(spec, x, y);
      break;

    case "line":
      spec.mark = { type: "line", point: true, tooltip: true };
      spec.encoding.x = xEncoding(x, fieldTitle(x), { sort: "ascending" });
      spec.encoding.y = quantitativeEncoding(y);
      if (color) {
        spec.encoding.color = { field: color, type: "nominal", title: fieldTitle(color) };
        spec.encoding.detail = { field: color };
      }
      spec.encoding.tooltip = tooltipFields(x, y, color);
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
    order_dow: "Day of week",
    order_hour: "Hour",
    review_score: "Review score",
    review_bucket: "Review bucket",
    default_is_low_score: "Default low score",
    is_high_score: "High score",
    customer_state: "State",
    product_category: "Category",
    delivery_days: "Delivery days",
    estimated_delivery_days: "Estimated delivery days",
    delivery_delay_days: "Delay days",
    delivery_speed_bucket: "Delivery speed",
    is_late: "Late delivery",
    delivery_status_bucket: "Delivery status",
    delay_bucket: "Delay bucket",
    revenue: "Revenue",
    order_item_revenue: "Item revenue",
    revenue_bucket: "Revenue bucket",
    item_count: "Item count",
    product_count: "Product count",
    category_count: "Category count",
    seller_count: "Seller count",
    freight_total: "Freight",
    avg_item_price: "Avg item price",
    freight_ratio: "Freight ratio",
    freight_bucket: "Freight bucket",
    order_size_bucket: "Order size",
    primary_payment_type: "Payment type",
    payment_method_count: "Payment methods",
    max_payment_installments: "Max installments",
    primary_payment_installments: "Primary installments",
    order_count: "Orders",
    low_score_ratio: "Low-score share",
    late_ratio: "Late share",
    on_time_ratio: "On-time share",
    high_score_ratio: "High-score share",
    avg_freight_ratio: "Avg freight ratio",
  };
  return titles[field] || field;
}

function isRatioField(field) {
  return RATIO_FIELDS.has(field);
}

function addRatioTooltip(spec, x, y) {
  if (!isRatioField(y)) return;
  const countField = RATIO_COUNT_FIELDS[y];
  spec.encoding.tooltip = [
    { field: x, title: fieldTitle(x) },
    { field: y, type: "quantitative", title: fieldTitle(y), format: ".1%" },
    ...(countField
      ? [
          { field: countField.field, type: "quantitative", title: countField.title },
          { field: "order_count", type: "quantitative", title: "Orders" },
        ]
      : []),
  ];
}

function tooltipFields(x, y, color) {
  const fields = [
    { field: x, title: fieldTitle(x) },
    ...(color ? [{ field: color, type: "nominal", title: fieldTitle(color) }] : []),
    {
      field: y,
      type: "quantitative",
      title: fieldTitle(y),
      format: isRatioField(y) ? ".1%" : undefined,
    },
  ];
  const countField = RATIO_COUNT_FIELDS[y];
  if (countField) {
    fields.push(
      { field: countField.field, type: "quantitative", title: countField.title },
      { field: "order_count", type: "quantitative", title: "Orders" },
    );
  }
  return fields.map(stripUndefined);
}

function stripUndefined(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, value]) => value !== undefined));
}
