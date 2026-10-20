<script setup lang="ts">
import { computed } from "vue"
import { useData } from "vitepress"

const { theme } = useData()
const latest = computed(
  () => (theme.value as { docLatest?: string }).docLatest || "",
)
const current = computed(
  () => (theme.value as { docCurrent?: string }).docCurrent || latest.value,
)
const show = computed(() => Boolean(latest.value && current.value && current.value !== latest.value))
</script>

<template>
  <div v-if="show" class="vp-version-banner">
    You are reading docs for <strong>v{{ current }}</strong>.
    The latest release is
    <a href="/docs/">v{{ latest }}</a>.
  </div>
</template>

<style scoped>
.vp-version-banner {
  padding: 10px 24px;
  background: var(--vp-c-warning-soft);
  color: var(--vp-c-text-1);
  border-bottom: 1px solid var(--vp-c-divider);
  font-size: 14px;
  text-align: center;
}
.vp-version-banner a {
  font-weight: 600;
  text-decoration: underline;
}
</style>
