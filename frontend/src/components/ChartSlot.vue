<template>
  <div
    class="chart-slot"
    :class="{ 'chart-slot--highlighted': view.highlighted, 'chart-slot--dimmed': isDimmed }"
  >
    <div class="chart-slot__header">
      <div class="chart-slot__heading">
        <div class="chart-slot__summary" aria-label="View summary">
          <div class="chart-slot__summary-main">
            <span class="chart-slot__identity">{{ viewLabel }}</span>
            <span class="chart-slot__chart-type">{{ chartTypeLabel }}</span>
          </div>
          <div v-if="viewBadges.length" class="chart-slot__badges" aria-label="View state">
            <span
              v-for="badge in viewBadges"
              :key="badge.key"
              class="chart-slot__badge"
              :class="`chart-slot__badge--${badge.tone}`"
              :title="badge.title"
              :aria-label="`${badge.label}: ${badge.value}`"
            >
              {{ badge.value }}
            </span>
          </div>
        </div>
        <span class="chart-slot__title">{{ view.title }}</span>
      </div>
    </div>

    <div v-if="isTableView" class="chart-slot__table-wrap">
      <table
        v-if="tableRows.length && tableColumns.length"
        class="chart-slot__table"
        :style="{ minWidth: tableMinWidth }"
      >
        <thead>
          <tr>
            <th v-for="column in tableColumns" :key="column.key" scope="col">
              {{ column.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIndex) in tableRows" :key="rowKey(row, rowIndex)">
            <td
              v-for="column in tableColumns"
              :key="column.key"
              :class="{ 'chart-slot__table-cell--numeric': isNumeric(row[column.field]) }"
              :title="cellTitle(row[column.field])"
            >
              {{ formatCellValue(row[column.field]) }}
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="chart-slot__empty">No table data</div>
    </div>

    <div v-else ref="vegaContainer" class="chart-slot__chart"></div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import vegaEmbed from "vega-embed";
import { createSpec } from "../specFactory";
import { useDashboardStore } from "../stores/dashboard";

const props = defineProps({
  view: { type: Object, required: true },
});

const FIELD_LABELS = {
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
  state_revenue: "State revenue",
};

const CHART_TYPE_LABELS = {
  bar: "Bar chart",
  line: "Line chart",
  scatter: "Scatter plot",
  histogram: "Histogram",
  pie: "Pie chart",
  table: "Table",
};

const store = useDashboardStore();
const vegaContainer = ref(null);
let vegaView = null;

const isDimmed = ref(false);
const isTableView = computed(() => props.view.chart_type === "table");
const viewLabel = computed(() => formatViewLabel(props.view.label || props.view.id));
const chartTypeLabel = computed(() => CHART_TYPE_LABELS[props.view.chart_type] || humanizeField(props.view.chart_type));
const tableRows = computed(() => (Array.isArray(props.view.data) ? props.view.data : []));
const tableColumns = computed(() => {
  const configured = normalizeConfiguredColumns(props.view.table_columns);
  if (configured.length) return configured;

  const fields = [];
  const seen = new Set();
  for (const row of tableRows.value) {
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    for (const field of Object.keys(row)) {
      if (seen.has(field)) continue;
      seen.add(field);
      fields.push(field);
    }
  }

  return fields.map((field) => ({
    key: field,
    field,
    label: fieldLabel(field),
  }));
});
const tableMinWidth = computed(() => `${Math.max(420, tableColumns.value.length * 132)}px`);

const viewBadges = computed(() => {
  const badges = [];
  const scope = props.view.filter_scope || inferScope(props.view);

  badges.push(scopeBadge(scope, props.view));

  if (props.view.limit) {
    badges.push({
      key: "limit",
      label: "Limit",
      value: `Top ${props.view.limit}`,
      tone: "neutral",
      title: `Only the top ${props.view.limit} rows after sorting are shown.`,
    });
  }

  const sort = sortMeta(props.view);
  if (sort.field) {
    badges.push({
      key: "sort",
      label: "Sort",
      value: `${fieldLabel(sort.field)} ${sort.direction}`,
      tone: "sort",
      title: `Sorted by ${fieldLabel(sort.field)} in ${sort.order === "asc" ? "ascending" : "descending"} order.`,
    });
  }

  if (usesLowScoreDefinition(props.view)) {
    badges.push({
      key: "low-score",
      label: "Low score",
      value: `<= ${props.view.low_score_threshold || 2}`,
      tone: "metric",
      title: `Low-score definition: review_score <= ${props.view.low_score_threshold || 2}.`,
    });
  }

  if (props.view.color) {
    badges.push({
      key: "split",
      label: "Split",
      value: fieldLabel(props.view.color),
      tone: "neutral",
      title: `Series split by ${fieldLabel(props.view.color)}.`,
    });
  }

  return badges;
});

watch(
  () => store.highlightedViewIds,
  (highlightedIds) => {
    const ids = Array.isArray(highlightedIds) ? highlightedIds : [];
    isDimmed.value = Boolean(ids.length && !ids.includes(props.view.id));
  },
  { deep: true, immediate: true }
);

watch(
  () => props.view,
  () => {
    nextTick(render);
  },
  { deep: true }
);

onMounted(() => {
  nextTick(render);
});

onBeforeUnmount(() => {
  clearVega();
});

async function render() {
  if (isTableView.value) {
    clearVega();
    return;
  }

  if (!vegaContainer.value) return;

  clearVega();
  const spec = createSpec(props.view);
  spec.data = { values: props.view.data || [] };

  try {
    const result = await vegaEmbed(vegaContainer.value, spec, {
      actions: false,
      renderer: "svg",
      theme: "vox",
    });
    vegaView = result.view;
  } catch (e) {
    console.warn("Vega render error:", e);
  }
}

function clearVega() {
  if (vegaView?.finalize) {
    vegaView.finalize();
  }
  vegaView = null;
  if (vegaContainer.value) {
    vegaContainer.value.innerHTML = "";
  }
}

function scopeBadge(scope, view) {
  if (scope === "frozen_snapshot") {
    return {
      key: "scope",
      label: "Scope",
      value: "Frozen snapshot",
      tone: "fixed",
      title: `Uses the filters captured when this view was created: ${filterSummary(view.snapshot_filters || view.effective_filters)}.`,
    };
  }
  if (scope === "fixed_condition") {
    return {
      key: "scope",
      label: "Scope",
      value: "Fixed conditions",
      tone: "fixed",
      title: filterSummary(view.filters),
    };
  }
  if (scope === "local_plus_global") {
    return {
      key: "scope",
      label: "Scope",
      value: "Local",
      tone: "mixed",
      title: `Local conditions: ${filterSummary(view.filters)}. Also follows global filters.`,
    };
  }
  if (scope === "independent") {
    return {
      key: "scope",
      label: "Scope",
      value: "Independent",
      tone: "fixed",
      title: "This view does not follow global filters.",
    };
  }
  return {
    key: "scope",
    label: "Scope",
    value: "Follows global",
    tone: "global",
    title: "This view updates with the current global filters.",
  };
}

function sortMeta(view) {
  const field = view.sort_by || inferSortField(view);
  if (!field) return { field: null, order: null, direction: "" };

  const order = view.sort_order || inferSortOrder(view, field);
  return {
    field,
    order,
    direction: order === "asc" ? "\u2191" : "\u2193",
  };
}

function inferSortField(view) {
  if (view.chart_type === "line" || isTimeField(view.x_field)) return view.x_field;
  if (view.x_field === "review_score") return view.x_field;
  return view.y_field;
}

function inferSortOrder(view, field) {
  if (view.chart_type === "line" || isTimeField(field) || field === view.x_field) return "asc";
  return "desc";
}

function usesLowScoreDefinition(view) {
  if (view.y_field === "low_score_ratio") return true;
  return Boolean(view.filters?.some((filter) => filter.field === "review_score"));
}

function isTimeField(field) {
  return ["order_month", "order_week", "order_date", "order_dow", "order_hour"].includes(field);
}

function normalizeConfiguredColumns(columns) {
  if (!Array.isArray(columns)) return [];

  return columns
    .map((column, index) => {
      if (typeof column === "string") {
        return {
          key: column,
          field: column,
          label: fieldLabel(column),
        };
      }

      if (!column || typeof column !== "object") return null;
      const field = column.field || column.key || column.name || column.id;
      if (!field) return null;

      return {
        key: `${field}-${index}`,
        field,
        label: column.label || column.title || fieldLabel(field),
      };
    })
    .filter(Boolean);
}

function rowKey(row, index) {
  return row?.id || row?.key || `${props.view.id || "table"}-${index}`;
}

function isNumeric(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function cellTitle(value) {
  const formatted = formatCellValue(value);
  return formatted === "" ? undefined : formatted;
}

function formatCellValue(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") {
    return Number.isFinite(value)
      ? value.toLocaleString(undefined, { maximumFractionDigits: 4 })
      : "";
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value instanceof Date) return value.toLocaleString();
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function inferScope(view) {
  if (view.freeze) return "frozen_snapshot";
  if (view.filters?.length && view.inherit_global_filters === false) return "fixed_condition";
  if (view.filters?.length) return "local_plus_global";
  if (view.inherit_global_filters === false) return "independent";
  return "global";
}

function filterSummary(filters = []) {
  if (!filters?.length) return "No fixed conditions";
  return filters.map((f) => `${fieldLabel(f.field)} ${operatorLabel(f.operator)} ${formatValue(f.value)}`).join("; ");
}

function formatValue(value) {
  if (Array.isArray(value)) return value.join(", ");
  return value ?? "";
}

function operatorLabel(operator) {
  const labels = {
    eq: "=",
    neq: "!=",
    in: "in",
    gte: ">=",
    lte: "<=",
    between: "between",
  };
  return labels[operator] || operator;
}

function fieldLabel(field) {
  return FIELD_LABELS[field] || humanizeField(field);
}

function formatViewLabel(label) {
  const text = String(label || "").trim();
  const match = text.match(/^view[-\s]?(\d+)$/i);
  if (match) return `View ${match[1]}`;
  return humanizeField(text || "view");
}

function humanizeField(field) {
  return String(field || "")
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
</script>

<style scoped>
.chart-slot {
  border: 1px solid #d0d7de;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
  transition: opacity 0.3s ease, box-shadow 0.3s ease;
}

.chart-slot--highlighted {
  box-shadow: 0 0 0 3px #3b82f6;
  opacity: 1 !important;
}

.chart-slot--dimmed {
  opacity: 0.4;
}

.chart-slot__header {
  display: flex;
  align-items: flex-start;
  min-width: 0;
  margin-bottom: 9px;
}

.chart-slot__heading {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}

.chart-slot__summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
  width: 100%;
}

.chart-slot__summary-main {
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 6px;
  min-width: 0;
}

.chart-slot__identity,
.chart-slot__chart-type {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 750;
  line-height: 1;
  white-space: nowrap;
}

.chart-slot__identity {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}

.chart-slot__chart-type {
  border: 1px solid #d7e1ee;
  background: #f8fafc;
  color: #475569;
}

.chart-slot__title {
  color: #1f2937;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.chart-slot__badges {
  display: flex;
  flex: 1 1 auto;
  flex-wrap: nowrap;
  gap: 5px;
  justify-content: flex-end;
  margin-left: auto;
  min-width: 0;
}

.chart-slot__badge {
  display: inline-flex;
  align-items: center;
  max-width: 150px;
  min-height: 22px;
  padding: 2px 7px;
  border: 1px solid #d7e1ee;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  font-size: 11px;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 750;
}

.chart-slot__badge--global {
  border-color: #bdd7c9;
  background: #f2fbf6;
  color: #17603a;
}

.chart-slot__badge--fixed {
  border-color: #f2c7a0;
  background: #fff7ed;
  color: #9a4b12;
}

.chart-slot__badge--mixed {
  border-color: #b8d4f8;
  background: #eff6ff;
  color: #1d4ed8;
}

.chart-slot__badge--sort {
  border-color: #d6d3f5;
  background: #f5f3ff;
  color: #5b21b6;
}

.chart-slot__badge--metric {
  border-color: #fecaca;
  background: #fff1f2;
  color: #be123c;
}

.chart-slot__badge--neutral {
  border-color: #d7e1ee;
  background: #f8fafc;
  color: #334155;
}

.chart-slot__chart {
  min-height: 200px;
}

.chart-slot__chart :deep(svg) {
  width: 100%;
}

.chart-slot__table-wrap {
  max-height: 280px;
  min-height: 120px;
  overflow: auto;
  border: 1px solid #e1e8f2;
  border-radius: 8px;
  background: #ffffff;
}

.chart-slot__table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
  color: #1f2937;
  font-size: 12px;
  line-height: 1.35;
}

.chart-slot__table th,
.chart-slot__table td {
  min-width: 0;
  padding: 7px 9px;
  border-right: 1px solid #edf2f7;
  border-bottom: 1px solid #edf2f7;
  overflow-wrap: anywhere;
  vertical-align: top;
}

.chart-slot__table th:last-child,
.chart-slot__table td:last-child {
  border-right: 0;
}

.chart-slot__table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f8fbff;
  color: #475569;
  font-size: 11px;
  font-weight: 750;
  text-align: left;
}

.chart-slot__table tbody tr:nth-child(even) {
  background: #fbfdff;
}

.chart-slot__table tbody tr:hover {
  background: #eff6ff;
}

.chart-slot__table-cell--numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.chart-slot__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  padding: 18px;
  color: #64748b;
  font-size: 13px;
}
</style>
