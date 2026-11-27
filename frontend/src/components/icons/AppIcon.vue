<template>
  <span
    class="app-icon"
    :class="{ 'app-icon--svg': loaded && loaded.paths.length }"
    :style="style"
    :title="tooltip"
    :role="decorative ? undefined : 'img'"
    :aria-label="decorative ? undefined : tooltip"
    :aria-hidden="decorative ? 'true' : undefined"
  >
    <svg
      v-if="loaded && loaded.paths.length"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      :stroke-width="strokeWidth"
      stroke-linecap="round"
      stroke-linejoin="round"
      focusable="false"
      aria-hidden="true"
    >
      <path v-for="(d, i) in loaded.paths" :key="i" :d="d" />
    </svg>
    <span v-else class="app-icon__fallback" aria-hidden="true">{{ meta.glyph }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { iconMeta, loadIcon } from './registry'
import type { AppIconDefinition } from './types'

const props = withDefaults(defineProps<{
  name: string
  size?: number | string
  color?: string
  strokeWidth?: number
  label?: string
  decorative?: boolean
}>(), {
  size: 18,
  color: '',
  strokeWidth: 1.8,
  label: '',
  decorative: false,
})

const meta = computed(() => iconMeta(props.name))
const loaded = ref<AppIconDefinition | null>(null)
const tooltip = computed(() => props.label || meta.value.label)

const style = computed(() => {
  const size = typeof props.size === 'number' ? `${props.size}px` : props.size
  return {
    width: size,
    height: size,
    color: props.color || undefined,
  }
})

async function resolve() {
  const name = props.name
  loaded.value = await loadIcon(name)
  if (props.name !== name) await resolve()
}

watch(() => props.name, resolve)
onMounted(resolve)
</script>

<style scoped>
.app-icon { display: inline-flex; align-items: center; justify-content: center; flex: none; line-height: 1; color: var(--icon-color, currentColor); }
.app-icon svg { width: 100%; height: 100%; display: block; }
.app-icon__fallback { font-size: 78%; font-style: normal; }
</style>
