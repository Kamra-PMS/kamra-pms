<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import { useData } from "vitepress"

type DocVersion = { version: string; label: string; path: string }

const { theme } = useData()
const open = ref(false)
const versions = computed<DocVersion[]>(
  () => (theme.value as { docVersions?: DocVersion[] }).docVersions || [],
)
const latest = computed(
  () => (theme.value as { docLatest?: string }).docLatest || "",
)
const current = computed(
  () => (theme.value as { docCurrent?: string }).docCurrent || latest.value,
)
const currentLabel = computed(() => {
  const hit = versions.value.find((v) => v.version === current.value)
  return hit?.label || current.value || "Version"
})

function hrefFor(v: DocVersion): string {
  // Absolute site paths so archived builds can jump to latest and peers
  if (v.path === "/" || v.path === "") return "/docs/"
  return `/docs${v.path.startsWith("/") ? v.path : `/${v.path}`}${
    v.path.endsWith("/") ? "" : "/"
  }`
}

function isCurrent(v: DocVersion): boolean {
  return v.version === current.value
}

const close = () => {
  open.value = false
}
onMounted(() => window.addEventListener("click", close))
onBeforeUnmount(() => window.removeEventListener("click", close))
</script>

<template>
  <div class="vp-version-switcher" @click.stop>
    <button
      type="button"
      class="vp-version-btn"
      :aria-expanded="open ? 'true' : 'false'"
      aria-haspopup="listbox"
      @click="open = !open"
    >
      <span class="vp-version-label">{{ currentLabel }}</span>
      <span class="vp-version-caret" aria-hidden="true">▾</span>
    </button>
    <ul v-if="open" class="vp-version-menu" role="listbox">
      <li v-for="v in versions" :key="v.version" role="option">
        <a
          class="vp-version-item"
          :class="{ active: isCurrent(v) }"
          :href="hrefFor(v)"
          >{{ v.label }}</a
        >
      </li>
    </ul>
  </div>
</template>

<style scoped>
.vp-version-switcher {
  position: relative;
  display: flex;
  align-items: center;
  margin-right: 8px;
}
.vp-version-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.vp-version-btn:hover {
  border-color: var(--vp-c-brand-1);
}
.vp-version-caret {
  font-size: 11px;
  opacity: 0.7;
}
.vp-version-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 168px;
  margin: 0;
  padding: 6px;
  list-style: none;
  border: 1px solid var(--vp-c-divider);
  border-radius: 10px;
  background: var(--vp-c-bg);
  box-shadow: var(--vp-shadow-3);
  z-index: 100;
}
.vp-version-item {
  display: block;
  padding: 8px 10px;
  border-radius: 6px;
  color: var(--vp-c-text-1);
  text-decoration: none;
  font-size: 13px;
  white-space: nowrap;
}
.vp-version-item:hover,
.vp-version-item.active {
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-brand-1);
}
</style>
