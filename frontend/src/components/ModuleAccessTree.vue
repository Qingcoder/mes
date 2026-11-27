<template>
  <div class="access-tree">
    <div v-if="!items.length" class="tree-empty">当前角色无可访问模块</div>
    <div v-for="group in groups" :key="group.name" class="tree-group">
      <div class="tree-node group-node">
        <span class="twisty">▾</span><b>{{ group.name }}</b><span class="count">{{ group.items.length }}</span>
      </div>
      <div class="tree-children">
        <button
          v-for="item in group.items"
          :key="item.path"
          type="button"
          class="tree-node leaf-node"
          @click="emit('select', item.path)"
        >
          <span class="leaf">└</span><span>{{ item.label }}</span><code class="mono">{{ item.path }}</code>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { routesForPermissions } from '../config/moduleAccess'

const props = defineProps<{ permissions?: string[] }>()
const emit = defineEmits<{ select: [path: string] }>()

const items = computed(() => routesForPermissions(props.permissions || []))
const groups = computed(() => {
  const map = new Map<string, any[]>()
  items.value.forEach(item => {
    if (!map.has(item.group)) map.set(item.group, [])
    map.get(item.group)!.push(item)
  })
  return Array.from(map, ([name, nodes]) => ({ name, items: nodes }))
})
</script>

<style scoped>
.access-tree { border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: #fff; max-height: 260px; overflow: auto; }
.tree-empty { color: var(--muted); font-size: 12px; padding: 12px; text-align: center; }
.tree-group + .tree-group { margin-top: 8px; }
.tree-node { display: flex; align-items: center; gap: 6px; width: 100%; font-size: 12px; padding: 5px 6px; border-radius: 5px; }
.group-node { color: var(--ink); font-weight: 700; }
.twisty, .leaf { color: var(--muted); flex: none; }
.count { margin-left: auto; color: var(--muted); font-weight: 400; }
.tree-children { padding-left: 14px; }
.leaf-node { border: 0; background: transparent; color: var(--gray); cursor: pointer; text-align: left; font-family: inherit; }
.leaf-node:hover { background: var(--tech-blue-soft); color: var(--tech-blue); }
.leaf-node code { margin-left: auto; color: var(--muted); font-size: 11px; }
</style>
