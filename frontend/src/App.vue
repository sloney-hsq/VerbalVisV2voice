<template>
  <Dashboard />
  <RuntimeStatus />
</template>

<script setup>
import Dashboard from "./components/Dashboard.vue";
import RuntimeStatus from "./components/RuntimeStatus.vue";
</script>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background: #fff;
  width: 100vw;
  height: 100dvh;
  min-height: 100dvh;
  overflow: hidden;
}

#app {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
</style>
