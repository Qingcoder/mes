<template>
  <div class="flow-combo">
    <div class="combo-head">
      <b>流程组合（按过站顺序）</b>
      <span class="mini">可勾选多条流程，系统按右侧顺序合并站点</span>
    </div>

    <div v-if="!options.length" class="mini empty-text">暂无已配置流程，请先在工艺管理中配好站点流程。</div>

    <div v-else class="combo-body">
      <div class="combo-picker">
        <div v-for="group in groupedOptions" :key="group.name" class="picker-group">
          <div class="picker-group-title">{{ group.name }}</div>
          <label v-for="flow in group.items" :key="flow.key" class="picker-item" :class="{ active: isSelected(flow.key) }">
            <input type="checkbox" :checked="isSelected(flow.key)" @change="toggle(flow.key)" />
            <span class="picker-item-main">
              <b>{{ flow.name }}</b>
              <small>{{ flow.stations.join(' → ') || '无站点' }}</small>
            </span>
            <span class="mini">{{ flow.stations.length }} 站</span>
          </label>
        </div>
      </div>

      <div class="combo-order">
        <div class="picker-group-title">组合顺序</div>
        <div v-if="!selected.length" class="mini empty-text">未选择流程</div>
        <div v-for="(flow, index) in selected" :key="flow.key" class="order-item">
          <span class="order-index">{{ index + 1 }}</span>
          <span class="order-main">
            <b>{{ flow.name }}</b>
            <small>{{ flow.stations.join(' → ') }}</small>
          </span>
          <span class="order-ops">
            <button class="link" type="button" :disabled="index === 0" @click="move(index, -1)">上移</button>
            <button class="link" type="button" :disabled="index === selected.length - 1" @click="move(index, 1)">下移</button>
            <button class="link danger-link" type="button" @click="remove(flow.key)">移除</button>
          </span>
        </div>
      </div>
    </div>

    <div v-if="mergedStations.length" class="flow-preview">
      <span v-for="(station, index) in mergedStations" :key="station + index"><b>{{ index + 1 }}</b>{{ station }}</span>
    </div>
    <p v-if="duplicateCount" class="mini">合并后有 {{ duplicateCount }} 个重复站点按首次出现保留。</p>
    <p v-else-if="!mergedStations.length" class="mini">请至少勾选一条流程。</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FlowOption, WoFlowSelection } from '../types/flow'

const props = withDefaults(defineProps<{
  /** 可选流程列表 */
  options: FlowOption[]
  /** 已选流程 key，顺序即组合顺序 */
  modelValue: string[]
}>(), { modelValue: () => [] })

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
  (e: 'update:stations', value: string[]): void
  (e: 'update:flows', value: WoFlowSelection[]): void
}>()

const groupedOptions = computed(() => {
  const groups: { name: string; items: FlowOption[] }[] = [
    { name: '工艺流程', items: [] },
    { name: '历史工单流程', items: [] },
  ]
  props.options.forEach(flow => {
    const target = flow.source === 'history' ? groups[1] : groups[0]
    target.items.push(flow)
  })
  return groups.filter(group => group.items.length)
})

const selected = computed<FlowOption[]>(() => props.modelValue
  .map(key => props.options.find(flow => flow.key === key))
  .filter((flow): flow is FlowOption => !!flow))

/** 合并后的站点序列：按流程顺序拼接，重复站点保留首次出现。 */
const mergedStations = computed<string[]>(() => {
  const merged: string[] = []
  const seen = new Set<string>()
  selected.value.forEach(flow => flow.stations.forEach(station => {
    const name = String(station || '').trim()
    if (!name || seen.has(name)) return
    seen.add(name)
    merged.push(name)
  }))
  return merged
})

const duplicateCount = computed(() => {
  const total = selected.value.reduce((sum, flow) => sum + flow.stations.length, 0)
  return total - mergedStations.value.length
})

function isSelected(key: string) { return props.modelValue.includes(key) }

function toggle(key: string) {
  const next = isSelected(key) ? props.modelValue.filter(item => item !== key) : [...props.modelValue, key]
  emit('update:modelValue', next)
  sync(next)
}
function remove(key: string) {
  const next = props.modelValue.filter(item => item !== key)
  emit('update:modelValue', next)
  sync(next)
}
function move(index: number, offset: number) {
  const next = [...props.modelValue]
  const target = index + offset
  if (target < 0 || target >= next.length) return
  const [item] = next.splice(index, 1)
  next.splice(target, 0, item)
  emit('update:modelValue', next)
  sync(next)
}

/** 勾选或排序变化都要重算合并结果与流程明细。 */
function sync(keys: string[]) {
  const flows: WoFlowSelection[] = keys
    .map(key => props.options.find(flow => flow.key === key))
    .filter((flow): flow is FlowOption => !!flow)
    .map(flow => ({ key: flow.key, name: flow.name, stations: [...flow.stations] }))
  emit('update:stations', mergedStations.value)
  emit('update:flows', flows)
}
</script>

<style scoped>
.flow-combo { display: grid; gap: 8px; }
.combo-head { display: flex; align-items: baseline; gap: 8px; }
.combo-body { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; }
.picker-group { display: grid; gap: 4px; margin-bottom: 8px; }
.picker-group-title { color: var(--muted); font-size: 11px; }
.picker-item { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 7px; padding: 7px 9px; cursor: pointer; }
.picker-item:hover { border-color: var(--tech-blue-line); background: var(--tech-blue-soft); }
.picker-item.active { border-color: var(--tech-blue); background: var(--tech-blue-soft); }
.picker-item input { width: auto; }
.picker-item-main { display: grid; gap: 2px; min-width: 0; flex: 1; }
.picker-item-main b { font-size: 12px; }
.picker-item-main small { color: var(--muted); font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.combo-order { display: grid; gap: 5px; align-content: start; }
.order-item { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 7px; padding: 6px 9px; }
.order-index { display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; background: var(--tech-blue); color: var(--white); font-size: 10px; flex: none; }
.order-main { display: grid; gap: 2px; min-width: 0; flex: 1; }
.order-main b { font-size: 12px; }
.order-main small { color: var(--muted); font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.order-ops { display: flex; gap: 6px; flex: none; }
.flow-preview { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.flow-preview span { display: inline-flex; align-items: center; gap: 5px; border: 1px solid var(--tech-blue-line); background: var(--tech-blue-soft); color: var(--tech-blue); border-radius: 999px; padding: 4px 9px; font-size: 12px; }
.flow-preview b { display: inline-grid; place-items: center; width: 16px; height: 16px; border-radius: 50%; background: var(--tech-blue); color: var(--white); font-size: 10px; }
.empty-text { padding: 6px 0; }
.link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; font-family: inherit; font-size: 11px; padding: 0; }
.link:disabled { color: var(--muted); cursor: not-allowed; }
.danger-link { color: var(--red); }
@media (max-width: 860px) { .combo-body { grid-template-columns: 1fr; } }
</style>
