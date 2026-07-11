<template>
  <aside
    class="runtime-status"
    :class="[`runtime-status--${phase}`, { 'runtime-status--busy': toolRunning }]"
    aria-live="polite"
    aria-label="VerbalVis runtime status"
  >
    <div class="runtime-status__main">
      <span class="runtime-status__indicator" aria-hidden="true"></span>
      <div class="runtime-status__copy">
        <strong>{{ phaseLabel }}</strong>
        <span v-if="phaseDetail">{{ phaseDetail }}</span>
      </div>
    </div>

    <div class="runtime-status__metrics" aria-label="Dashboard scope summary">
      <span>{{ activeFilterCount }} filters</span>
      <span>{{ viewCount }} views</span>
      <span v-if="filteredRows !== null">{{ formatNumber(filteredRows) }} rows</span>
      <span>low score ≤ {{ dashboardState.low_score_threshold || 2 }}</span>
    </div>

    <p v-if="toolRunning" class="runtime-status__notice">
      Voice input is temporarily paused while the current dashboard operation completes.
    </p>

    <p v-else-if="lastToolError" class="runtime-status__error">
      {{ lastToolError }}
    </p>
  </aside>
</template>

<script setup>
import { storeToRefs } from "pinia";
import { useRuntimeStore } from "../stores/runtime";

const runtime = useRuntimeStore();
const {
  phase,
  toolRunning,
  dashboardState,
  filteredRows,
  lastToolError,
  phaseLabel,
  phaseDetail,
  activeFilterCount,
  viewCount,
} = storeToRefs(runtime);

function formatNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString() : String(value ?? "");
}
</script>

<style scoped>
.runtime-status {
  position: fixed;
  top: 76px;
  right: 20px;
  z-index: 50;
  width: min(360px, calc(100vw - 40px));
  padding: 12px 14px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.12);
  backdrop-filter: blur(12px);
  pointer-events: none;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.runtime-status__main {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.runtime-status__indicator {
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 999px;
  background: #64748b;
  box-shadow: 0 0 0 4px rgba(100, 116, 139, 0.12);
  flex: 0 0 auto;
}

.runtime-status__copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.runtime-status__copy strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.2;
}

.runtime-status__copy span {
  color: #475569;
  font-size: 11px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.runtime-status__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.runtime-status__metrics span {
  padding: 3px 7px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 10px;
  line-height: 1.2;
}

.runtime-status__notice,
.runtime-status__error {
  margin-top: 9px;
  font-size: 11px;
  line-height: 1.4;
}

.runtime-status__notice {
  color: #92400e;
}

.runtime-status__error {
  color: #b91c1c;
}

.runtime-status--ready .runtime-status__indicator {
  background: #16a34a;
  box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.12);
}

.runtime-status--listening .runtime-status__indicator,
.runtime-status--assistant_speaking .runtime-status__indicator {
  background: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.runtime-status--processing .runtime-status__indicator,
.runtime-status--reading_dashboard .runtime-status__indicator,
.runtime-status--updating_dashboard .runtime-status__indicator {
  background: #d97706;
  box-shadow: 0 0 0 4px rgba(217, 119, 6, 0.12);
  animation: runtime-pulse 1.25s ease-in-out infinite;
}

.runtime-status--error .runtime-status__indicator,
.runtime-status--disconnected .runtime-status__indicator {
  background: #dc2626;
  box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.12);
}

@keyframes runtime-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(0.72); opacity: 0.55; }
}

@media (max-width: 720px) {
  .runtime-status {
    top: auto;
    right: 12px;
    bottom: 12px;
    left: 12px;
    width: auto;
  }
}
</style>
