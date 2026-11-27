<template>
  <div class="auth-tabs" role="tablist">
    <button
      v-for="t in tabs"
      :key="t.value"
      type="button"
      role="tab"
      :aria-selected="modelValue === t.value"
      :class="{ active: modelValue === t.value }"
      @click="emit('update:modelValue', t.value)"
    >{{ t.label }}</button>
  </div>
</template>

<script setup lang="ts">
import { DEFAULT_AUTH_TABS, type AuthMode, type AuthTab } from '../types/auth'

withDefaults(defineProps<{
  modelValue: AuthMode
  tabs?: AuthTab[]
}>(), {
  tabs: () => DEFAULT_AUTH_TABS,
})

const emit = defineEmits<{
  'update:modelValue': [value: AuthMode]
}>()
</script>
