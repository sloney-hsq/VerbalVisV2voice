<template>
  <div
    class="chart-slot"
    :class="{ 'chart-slot--highlighted': view.highlighted, 'chart-slot--dimmed': isDimmed }"
  >
    <div class="chart-slot__header">
      <span class="chart-slot__title">{{ view.title }}</span>
      <span class="chart-slot__id">{{ view.label || view.id }}</span>
    </div>
    <div ref="vegaContainer" class="chart-slot__chart"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from "vue";
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

// Watch data changes
watch(() => props.view.data, render, { deep: true });

onMounted(() => {
  nextTick(render);
});
</script>

<style scoped>
.chart-slot {
  border: 1px solid #d0d7de;
  border-radius: 12px;
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
  align-items: center;
  margin-bottom: 8px;
}

.chart-slot__title {
  font-weight: 600;
  font-size: 14px;
  color: #1f2937;
}

.chart-slot__id {
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
