<template>
  <div class="fixed-module-notice">
    <div class="title-row">
      <span class="module-icon"><AppIcon :name="module.icon" :size="18" :label="module.label" /></span>
      <div>
        <b>{{ module.label }}</b>
        <small>MES 业务模块 · 后续按需求迭代</small>
      </div>
      <span class="status">已预留</span>
    </div>
    <p>{{ module.description }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { fixedModuleByKey } from '../config/fixedModules'
import { AppIcon } from './icons'

const props = defineProps<{ moduleKey: string }>()
const module = computed(() => {
  const fixed = fixedModuleByKey(props.moduleKey)
  return fixed
    ? fixed
    : { key: props.moduleKey, label: props.moduleKey, route: '', icon: 'default', permission: '', order: 0, description: 'MES 业务模块，后续按需求迭代。' }
})
</script>

<style scoped>
.fixed-module-notice { border: 1px dashed var(--tech-blue-line); border-left: 3px solid var(--tech-blue); background: var(--tech-blue-soft); border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; }
.title-row { display: flex; align-items: center; gap: 10px; }
.module-icon { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 7px; background: var(--white); color: var(--tech-blue); font-weight: 700; }
.title-row b { display: block; font-size: 14px; }
.title-row small { display: block; color: var(--muted); font-size: 11px; margin-top: 2px; }
.status { margin-left: auto; border: 1px solid var(--tech-blue-line); color: var(--tech-blue); border-radius: 10px; padding: 2px 8px; font-size: 11px; }
.fixed-module-notice p { margin: 9px 0 0; font-size: 12px; color: var(--muted); line-height: 1.7; }
</style>
