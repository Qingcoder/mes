<template>
  <div class="org-tree">
    <button class="tree-root" type="button" :class="{ active: !selected.position && !selected.role }" @click="emit('select', { position: '', role: '' })">
      <span class="twisty" :title="rootOpen ? '收起全部岗位' : '展开全部岗位'" @click.stop="toggleRoot">{{ rootOpen ? '▾' : '▸' }}</span>
      <b>全部人员</b><span class="count">{{ persons.length }}</span>
    </button>

    <div v-for="pos in positions" v-show="rootOpen" :key="pos.name" class="pos-group">
      <div class="pos-head">
        <button class="tree-node pos" type="button" :class="{ active: selected.position === pos.name && !selected.role }" @click="emit('select', { position: pos.name, role: '' })">
          <span class="twisty" :title="isPositionOpen(pos.name) ? '收起角色' : '展开角色'" @click.stop="togglePosition(pos.name)">{{ isPositionOpen(pos.name) ? '▾' : '▸' }}</span>
          <b>{{ pos.name }}</b><span class="count">{{ pos.items.length }}</span>
        </button>
        <button
          v-if="canEdit && pos.name !== '未分配岗位'"
          class="pos-edit"
          type="button"
          title="编辑岗位名称"
          @click.stop="emit('edit', pos.name)"
        >编辑</button>
      </div>
      <div v-for="role in pos.roles" v-show="isPositionOpen(pos.name)" :key="role.name" class="role-group">
        <button class="tree-node role" type="button" :class="{ active: selected.position === pos.name && selected.role === role.name }" @click="emit('select', { position: pos.name, role: role.name })">
          <span>└</span><span>{{ role.name }}</span><span class="count">{{ role.items.length }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

const props = defineProps<{
  persons: any[]
  selected: { position: string; role: string }
  canEdit?: boolean
}>()
const emit = defineEmits<{
  select: [value: { position: string; role: string }]
  edit: [position: string]
}>()

const rootOpen = ref(true)
const positionOpen = reactive<Record<string, boolean>>({})
function toggleRoot() { rootOpen.value = !rootOpen.value }
function isPositionOpen(name: string) { return positionOpen[name] !== false }
function togglePosition(name: string) { positionOpen[name] = !isPositionOpen(name) }

const positions = computed(() => {
  const map = new Map<string, Map<string, any[]>>()
  props.persons.forEach(p => {
    const position = p.position || '未分配岗位'
    const role = p.role || '未分配角色'
    if (!map.has(position)) map.set(position, new Map())
    const roles = map.get(position)!
    if (!roles.has(role)) roles.set(role, [])
    roles.get(role)!.push(p)
  })
  return Array.from(map, ([name, roleMap]) => ({
    name,
    items: props.persons.filter(p => (p.position || '未分配岗位') === name),
    roles: Array.from(roleMap, ([roleName, items]) => ({ name: roleName, items })),
  }))
})
</script>

<style scoped>
.org-tree { border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #fff; }
.tree-root, .tree-node { display: flex; align-items: center; gap: 6px; width: 100%; border: 0; background: transparent; border-radius: 6px; padding: 7px 8px; cursor: pointer; font-family: inherit; font-size: 13px; text-align: left; color: var(--ink); }
.tree-root:hover, .tree-node:hover, .tree-root.active, .tree-node.active { background: var(--tech-blue-soft); color: var(--tech-blue); }
.tree-root b, .tree-node b { font-weight: 700; }
.twisty { display: inline-grid; place-items: center; width: 14px; flex: none; cursor: pointer; color: var(--muted); }
.twisty:hover { color: var(--tech-blue); }
.pos-group { margin-top: 4px; }
.pos-head { display: flex; align-items: center; gap: 4px; }
.pos-head .tree-node { min-width: 0; }
.pos-edit { flex: none; border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; font-family: inherit; font-size: 11px; padding: 4px; }
.pos-edit:hover { text-decoration: underline; }
.role-group { padding-left: 16px; }
.tree-node.role { color: var(--gray); }
.count { margin-left: auto; color: var(--muted); font-size: 11px; }
</style>
