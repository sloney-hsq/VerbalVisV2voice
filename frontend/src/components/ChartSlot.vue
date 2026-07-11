<template>
  <article
    class="chart-card"
    :class="{
      'chart-card--highlighted': view.highlighted,
      'chart-card--dimmed': isDimmed,
    }"
  >
    <header class="chart-card__header">
      <div class="chart-card__identity">
        <span class="view-id">{{ viewLabel }}</span>
        <span class="chart-type">{{ chartTypeLabel }}</span>
      </div>
      <div class="chart-card__badges">
        <span v-if="view.top_n || view.limit">Top {{ view.top_n || view.limit }}</span>
        <span v-if="usesLowScore">Low score ≤ 2</span>
        <span v-if="resolvedHighlight" class="highlight-badge">
          {{ resolvedHighlight.label }}
        </span>
      </div>
      <h2>{{ view.title }}</h2>
    </header>
    <div
      ref="vegaContainer"
      class="chart-card__body"
      :style="chartBodyStyle"
    ></div>
  </article>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import vegaEmbed from "vega-embed";
import { createSpec } from "../specFactory";
import { chartHeightForView } from "../chartLayout";
import { resolveHighlight } from "../highlightSpec";
import { useDashboardStore } from "../stores/dashboard";

const props = defineProps({
  view: { type: Object, required: true },
});

const store = useDashboardStore();
const vegaContainer = ref(null);
let embeddedView = null;

const activeHighlightElement = computed(() => (
  props.view.highlighted ? store.highlightElement : null
));
const resolvedHighlight = computed(() => (
  resolveHighlight(props.view, activeHighlightElement.value)
));
const isDimmed = computed(() => (
  store.highlightDimOthers &&
  store.highlightedViewIds.length > 0 &&
  !props.view.highlighted
));
const viewLabel = computed(() => {
  const match = String(props.view.id || "").match(/view(\d+)/i);
  return match ? `View ${match[1]}` : String(props.view.id || "View");
});
const chartTypeLabel = computed(() => ({
  line: "Line",
  bar: "Bar",
  scatter: "Scatter",
}[props.view.chart_type] || props.view.chart_type));
const usesLowScore = computed(() => (
  props.view.y_field === "low_score_ratio" ||
  (props.view.local_filters || props.view.filters || []).some(
    (filter) => filter.field === "review_score",
  )
));
const chartBodyStyle = computed(() => ({
  minHeight: `${chartHeightForView(props.view)}px`,
}));

watch(
  () => props.view,
  () => nextTick(render),
  { deep: true },
);
watch(
  activeHighlightElement,
  () => nextTick(render),
  { deep: true },
);

onMounted(() => nextTick(render));
onBeforeUnmount(clearChart);

async function render() {
  if (!vegaContainer.value) return;
  clearChart();

  const spec = createSpec(props.view, activeHighlightElement.value);
  spec.data = { values: props.view.data || [] };
  try {
    const result = await vegaEmbed(vegaContainer.value, spec, {
      actions: false,
      renderer: "svg",
      theme: "vox",
    });
    embeddedView = result.view;
  } catch (error) {
    console.warn(`Unable to render ${props.view.id}`, error);
    vegaContainer.value.textContent = "Unable to render this view.";
  }
}

function clearChart() {
  embeddedView?.finalize?.();
  embeddedView = null;
  if (vegaContainer.value) vegaContainer.value.innerHTML = "";
}
</script>

<style scoped>
.chart-card {
  display: flex;
  flex-direction: column;
  width: 100%;
  min-width: 0;
  min-height: 270px;
  padding: 8px 9px 7px;
  overflow: hidden;
  border: 1px solid #d9e1ec;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
  transition: opacity 160ms ease, box-shadow 160ms ease;
}

.chart-card--highlighted {
  box-shadow: 0 0 0 2px #3b82f6, 0 2px 8px rgba(37, 99, 235, 0.13);
}

.chart-card--dimmed {
  opacity: 0.28;
}

.chart-card__header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  min-height: 36px;
  gap: 3px 7px;
}

.chart-card__identity,
.chart-card__badges {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 5px;
}

.chart-card__badges {
  justify-content: flex-end;
  overflow: hidden;
}

.view-id,
.chart-type,
.chart-card__badges span {
  display: inline-flex;
  align-items: center;
  min-height: 19px;
  padding: 2px 6px;
  overflow: hidden;
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #f8fafc;
  color: #526174;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.view-id {
  border-color: #bfd7ff;
  background: #eff6ff;
  color: #1d4ed8;
}

.highlight-badge {
  max-width: 200px;
  border-color: #f4c85c !important;
  background: #fffbeb !important;
  color: #92400e !important;
}

.chart-card h2 {
  grid-column: 1 / -1;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: #1f2937;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chart-card__body {
  flex: 1 1 auto;
  width: 100%;
  min-width: 0;
  overflow: hidden;
}

.chart-card__body :deep(.vega-embed) {
  width: 100%;
  max-width: 100%;
}

.chart-card__body :deep(svg) {
  display: block;
  max-width: 100%;
}
</style>
