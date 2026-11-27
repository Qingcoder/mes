<template>
  <div class="function-tree-select">
    <div class="tree-summary">已选 {{ modelValue.length }} 项功能</div>
    <div v-if="!nodes.length" class="tree-empty">暂无可勾选功能，将使用系统默认权限。</div>
    <div v-for="group in nodes" :key="group.id" class="tree-group">
      <div class="group-row">
        <button class="twisty" type="button" :aria-label="`${open[group.id] ? '收起' : '展开'}${group.name}`"
                @click="toggleOpen(group.id)">
          {{ open[group.id] ? '▾' : '▸' }}
        </button>
        <input
          :ref="el => bindCheckbox(group.id, el)"
          type="checkbox"
          :checked="isGroupChecked(group)"
          :aria-label="`选择${group.name}全部功能`"
          @change="toggleGroup(group)"
        />
        <b>{{ group.name }}</b>
        <span class="count">{{ groupChildren(group).length }}</span>
      </div>
      <div v-if="open[group.id]" class="tree-children">
        <label v-for="leaf in groupChildren(group)" :key="leaf.id" class="leaf-row">
          <input type="checkbox" :value="leaf.id" :checked="modelValue.includes(leaf.id)" @change="toggleLeaf(leaf.id)" />
          <span>{{ leaf.name }}</span>
          <small class="mono">{{ leaf.permission }}</small>
          <em class="mono route-tag">{{ leaf.route || '无独立路由' }}</em>
        </label>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{
  nodes: any[]
  modelValue: string[]
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const open = ref<Record<string, boolean>>({})
const checkboxEls: Record<string, HTMLInputElement | null> = {}

function bindCheckbox(id: string, el: unknown) {
  checkboxEls[id] = el as HTMLInputElement | null
  nextTick(() => updateIndeterminate(id))
}

function collectLeafIds(node: any): string[] {
  const children = node?.children || []
  if (!children.length) return node?.id ? [node.id] : []
  return children.flatMap((child: any) => collectLeafIds(child))
}

function groupChildren(group: any): any[] {
  return group?.children || []
}

function isGroupChecked(group: any): boolean {
  const ids = collectLeafIds(group)
  return ids.length > 0 && ids.every(id => props.modelValue.includes(id))
}

function isGroupPartial(group: any): boolean {
  const ids = collectLeafIds(group)
  const selected = ids.filter(id => props.modelValue.includes(id)).length
  return selected > 0 && selected < ids.length
}

function updateIndeterminate(id: string) {
  const group = props.nodes.find(n => n.id === id)
  const el = checkboxEls[id]
  if (group && el) el.indeterminate = isGroupPartial(group)
}

function updateAllIndeterminate() {
  props.nodes.forEach(n => updateIndeterminate(n.id))
}

function toggleOpen(id: string) {
  open.value = { ...open.value, [id]: !open.value[id] }
}

function toggleGroup(group: any) {
  const ids = collectLeafIds(group)
  const allChecked = ids.every(id => props.modelValue.includes(id))
  const next = allChecked
    ? props.modelValue.filter(id => !ids.includes(id))
    : Array.from(new Set([...props.modelValue, ...ids]))
  emit('update:modelValue', next)
  nextTick(updateAllIndeterminate)
}

function toggleLeaf(id: string) {
  const next = props.modelValue.includes(id)
    ? props.modelValue.filter(x => x !== id)
    : [...props.modelValue, id]
  emit('update:modelValue', next)
  nextTick(updateAllIndeterminate)
}

watch(() => props.modelValue, updateAllIndeterminate, { deep: true, immediate: true })
watch(() => props.nodes, updateAllIndeterminate, { deep: true })
</script>

<style scoped>
.function-tree-select { border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: #fff; }
.tree-summary { font-size: 12px; color: var(--muted); margin-bottom: 8px; }
.tree-empty { border: 1px dashed var(--line); border-radius: 6px; padding: 12px; text-align: center; color: var(--muted); font-size: 12px; }
.tree-group + .tree-group { margin-top: 6px; border-top: 1px solid var(--line); padding-top: 6px; }
.group-row { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.group-row input, .leaf-row input { width: auto; }
.twisty { border: 0; background: transparent; color: var(--muted); cursor: pointer; width: 18px; }
.count { margin-left: auto; color: var(--muted); font-size: 11px; }
.tree-children { padding: 4px 0 2px 26px; }
.leaf-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; font-size: 12px; cursor: pointer; }
.leaf-row small { color: var(--muted); }
.route-tag { margin-left: auto; color: var(--muted); font-size: 11px; font-style: normal; }
</style>
