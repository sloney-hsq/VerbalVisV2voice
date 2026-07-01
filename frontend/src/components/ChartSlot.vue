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
    <div ref="vegaContainer" class="chart-slot__chart"></div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, nextTick } from "vue";
import vegaEmbed from "vega-embed";
import { createSpec } from "../specFactory";
import { useDashboardStore } from "../stores/dashboard";

const props = defineProps({
  view: { type: Object, required: true },
});

const store = useDashboardStore();
const vegaContainer = ref(null);
let vegaView = null;

const isDimmed = ref(false);

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

// Watch highlight state
watch(
  () => store.highlightedViewId,
  (hlId) => {
    if (hlId && hlId !== props.view.id) {
      isDimmed.value = true;
    } else {
      isDimmed.value = false;
    }
  }
);

// Render / re-render
async function render() {
  if (!vegaContainer.value) return;

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

// Watch data and metadata changes
watch(() => props.view, render, { deep: true });

onMounted(() => {
  nextTick(render);
});

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
  const labels = {
    order_month: "月份",
    order_week: "周",
    order_date: "日期",
    order_dow: "星期",
    order_hour: "小时",
    review_score: "评分",
    customer_state: "州",
    product_category: "品类",
    delivery_days: "配送天数",
    delivery_speed_bucket: "配送速度",
    revenue: "营收",
    order_count: "订单量",
    low_score_ratio: "低分占比",
  };
  return labels[field] || field;
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
  font-size: 11px;
  color: #9ca3af;
  font-family: monospace;
}

.chart-slot__chart {
  min-height: 200px;
}

.chart-slot__chart :deep(svg) {
  width: 100%;
}
</style>
