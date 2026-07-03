<template>
  <div
    class="chart-slot"
    :class="{ 'chart-slot--highlighted': view.highlighted, 'chart-slot--dimmed': isDimmed }"
  >
    <div class="chart-slot__header">
      <div class="chart-slot__heading">
        <span class="chart-slot__title">{{ view.title }}</span>
        <div v-if="viewBadges.length" class="chart-slot__badges" aria-label="View state">
          <span
            v-for="badge in viewBadges"
            :key="badge.key"
            class="chart-slot__badge"
            :class="`chart-slot__badge--${badge.tone}`"
            :title="badge.title"
          >
            {{ badge.label }}
          </span>
        </div>
      </div>
      <span class="chart-slot__id">{{ view.label || view.id }}</span>
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
      <div v-else class="chart-slot__empty">暂无表格数据</div>
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
  order_month: "月份",
  order_week: "周",
  order_date: "日期",
  order_dow: "星期",
  order_hour: "小时",
  review_score: "评分",
  review_bucket: "评分分组",
  default_is_low_score: "默认低分",
  is_high_score: "高评分",
  customer_state: "州",
  product_category: "品类",
  delivery_days: "配送天数",
  estimated_delivery_days: "预计配送天数",
  delivery_delay_days: "延迟天数",
  delivery_speed_bucket: "配送速度",
  is_late: "是否延迟",
  delivery_status_bucket: "配送状态",
  delay_bucket: "延迟程度",
  revenue: "营收",
  order_item_revenue: "商品收入",
  revenue_bucket: "营收分组",
  item_count: "商品件数",
  product_count: "商品种数",
  category_count: "品类数",
  seller_count: "卖家数",
  freight_total: "运费",
  avg_item_price: "平均商品价格",
  freight_ratio: "运费占比",
  freight_bucket: "运费分组",
  order_size_bucket: "订单规模",
  primary_payment_type: "支付方式",
  payment_method_count: "支付方式数",
  max_payment_installments: "最大分期数",
  primary_payment_installments: "主要支付分期数",
  order_count: "订单量",
  low_score_ratio: "低分占比",
  late_ratio: "延迟率",
  on_time_ratio: "准时率",
  high_score_ratio: "高评分占比",
  avg_freight_ratio: "平均运费占比",
  state_revenue: "州销售额",
};

const store = useDashboardStore();
const vegaContainer = ref(null);
let vegaView = null;

const isDimmed = ref(false);
const isTableView = computed(() => props.view.chart_type === "table");
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
  if (scope === "frozen_snapshot") {
    badges.push({
      key: "scope",
      label: "固定快照",
      tone: "fixed",
      title: `创建时口径: ${filterSummary(props.view.snapshot_filters || props.view.effective_filters)}`,
    });
  } else if (scope === "fixed_condition") {
    badges.push({
      key: "scope",
      label: "固定条件",
      tone: "fixed",
      title: filterSummary(props.view.filters),
    });
  } else if (scope === "local_plus_global") {
    badges.push({
      key: "scope",
      label: "局部 + 全局",
      tone: "mixed",
      title: `局部条件: ${filterSummary(props.view.filters)}；同时跟随全局筛选`,
    });
  } else if (scope === "independent") {
    badges.push({
      key: "scope",
      label: "独立视图",
      tone: "fixed",
      title: "不跟随全局筛选变化",
    });
  } else {
    badges.push({
      key: "scope",
      label: "跟随全局",
      tone: "global",
      title: "会跟随当前全局筛选变化",
    });
  }

  if (props.view.limit) {
    badges.push({
      key: "limit",
      label: `Top ${props.view.limit}`,
      tone: "neutral",
      title: `只显示排序后的前 ${props.view.limit} 项`,
    });
  }

  if (props.view.sort_by) {
    badges.push({
      key: "sort",
      label: `排序 ${fieldLabel(props.view.sort_by)} ${props.view.sort_order === "asc" ? "↑" : "↓"}`,
      tone: "neutral",
      title: `按 ${fieldLabel(props.view.sort_by)} ${props.view.sort_order === "asc" ? "从小到大" : "从大到小"} 排序`,
    });
  }

  if (props.view.y_field === "low_score_ratio" && props.view.low_score_threshold) {
    badges.push({
      key: "low-score",
      label: `低分 ≤ ${props.view.low_score_threshold}`,
      tone: "neutral",
      title: `低分口径: review_score <= ${props.view.low_score_threshold}`,
    });
  }

  return badges;
});

watch(
  () => store.highlightedViewId,
  (hlId) => {
    isDimmed.value = Boolean(hlId && hlId !== props.view.id);
  }
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
  if (typeof value === "boolean") return value ? "是" : "否";
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
  if (!filters?.length) return "无固定条件";
  return filters.map((f) => `${fieldLabel(f.field)} ${operatorLabel(f.operator)} ${formatValue(f.value)}`).join("；");
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

function humanizeField(field) {
  return String(field || "")
    .replace(/_/g, " ")
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
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.chart-slot__heading {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}

.chart-slot__title {
  font-weight: 600;
  font-size: 14px;
  color: #1f2937;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.chart-slot__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  min-width: 0;
}

.chart-slot__badge {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 22px;
  padding: 2px 7px;
  border: 1px solid #d7e1ee;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  font-size: 11px;
  line-height: 1.2;
  white-space: nowrap;
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
  color: #1d4f91;
}

.chart-slot__badge--neutral {
  border-color: #d7e1ee;
  background: #f8fafc;
  color: #475569;
}

.chart-slot__id {
  flex: 0 0 auto;
  max-width: 120px;
  overflow: hidden;
  color: #9ca3af;
  font-family: monospace;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  vertical-align: top;
  overflow-wrap: anywhere;
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
