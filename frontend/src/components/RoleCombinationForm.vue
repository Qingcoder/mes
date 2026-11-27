<template>
  <div ref="rootRef" :class="['combo-form', { compact }]" :aria-busy="loading || loadingConfig">
    <div v-if="loadingConfig" class="msg">正在加载模块注册表…</div>
    <div v-else-if="configError" class="msg err">{{ configError }}</div>

    <template v-else>
      <div class="field">
        <label>六大模块权限树</label>
        <p class="hint">勾选模块会选中其下全部子权限；也可单独选择子权限。后续新增到功能树的模块功能会自动出现在这里。</p>
        <div class="permission-tree">
          <div v-for="m in modules" :key="m.key" class="tree-group">
            <div class="tree-parent">
              <button class="tree-twisty" type="button" :aria-label="`${expanded[m.key] ? '收起' : '展开'}${m.name}`" @click="expanded[m.key] = !expanded[m.key]">
                {{ expanded[m.key] ? '▾' : '▸' }}
              </button>
              <input
                :ref="el => bindParentCheckbox(m.key, el)"
                type="checkbox"
                :checked="isModuleChecked(m)"
                :disabled="!!created || loading"
                @change="toggleModule(m)"
              />
              <b>{{ m.name }}</b>
              <small class="mono">{{ m.permission }}</small>
              <span class="count">{{ m.children?.length || 0 }}</span>
            </div>
            <div v-if="expanded[m.key]" class="tree-children">
              <label v-for="child in m.children || []" :key="child.id" class="tree-child">
                <input
                  type="checkbox"
                  :checked="selectedFunctions.includes(child.id)"
                  :disabled="!!created || loading"
                  @change="toggleFunction(m.key, child.id)"
                />
                <span>{{ child.name }}</span>
                <small class="mono">{{ child.permission }}</small>
                <em class="mono">{{ child.route || '无独立路由' }}</em>
              </label>
              <div v-if="!(m.children || []).length" class="tree-empty">该模块暂无子权限，新增到功能树后会自动显示。</div>
            </div>
          </div>
        </div>
        <p class="hint">选择完成后系统自动生成角色，无需提交。</p>
      </div>

      <div class="code-line">
        角色编码：<b class="mono">{{ comboCodePreview }}</b>
        <small>按模块位掩码生成，唯一且不可编辑</small>
      </div>

      <div v-if="!created" class="field">
        <label for="combo-role-name">角色名称</label>
        <input
          id="combo-role-name"
          v-model="name"
          maxlength="64"
          autocomplete="off"
          :disabled="!selectedModules.length || loading"
          :placeholder="selectedModules.length ? '输入名称后按回车或移开焦点即创建' : '请先选择模块权限'"
          @keydown.enter.prevent="createOnce"
          @blur="createOnce"
        />
      </div>

      <div v-if="loading && !created" class="msg">正在按当前组合生成默认角色…</div>

      <div v-if="created" class="created-panel">
        <div class="msg ok" role="status">
          {{ created.created ? '默认角色已创建' : '该权限组合角色已存在' }}：{{ created.avatar }} {{ created.code }} · {{ created.name }}
        </div>
        <div class="rename-row">
          <label for="combo-rename">角色名称（可编辑）</label>
          <input id="combo-rename" v-model="renameValue" maxlength="64" @keydown.enter.prevent="rename" @blur="rename" />
        </div>
        <div v-if="created.modules?.length" class="module-fields">
          <b>组合排列表字段</b>
          <div v-for="m in created.modules" :key="m.key" class="field-row">
            <span>{{ m.name }}</span>
            <small class="mono">key={{ m.key }} · order={{ m.order }} · permission={{ m.permission }} · route={{ m.route || '—' }}</small>
            <small class="mono">component={{ m.component || '—' }} · functionId={{ m.functionId || '—' }} · selected={{ m.selected }}</small>
            <em>{{ m.description }}</em>
            <div v-if="(m.children || []).length" class="created-children">
              <span v-for="child in m.children" :key="child.id" :class="{ on: child.selected }">
                {{ child.selected ? '✓' : '—' }} {{ child.name }}（{{ child.permission }}）
              </span>
            </div>
          </div>
        </div>
        <div class="msg">已生成 {{ created.permissions?.length || 0 }} 项权限、{{ generatedRoutes?.length || 0 }} 条路由配置</div>
      </div>

      <div v-if="error" class="msg err" role="alert">{{ error }}</div>

      <div v-if="showCancel" class="form-foot">
        <button class="btn" type="button" @click="emit('cancel')">关闭</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { api } from '../api'

const props = withDefaults(defineProps<{ showCancel?: boolean; compact?: boolean }>(), { showCancel: false, compact: false })
const emit = defineEmits<{ cancel: []; created: [value: any] }>()

const rootRef = ref<HTMLElement | null>(null)
const modules = ref<any[]>([])
const codePrefix = ref('RB')
const functionOrder = ref<string[]>([])
const selectedModules = ref<string[]>([])
const selectedFunctions = ref<string[]>([])
const expanded = ref<Record<string, boolean>>({})
const parentCheckboxes: Record<string, HTMLInputElement | null> = {}
const name = ref('')
const renameValue = ref('')
const created = ref<any>(null)
const generatedRoutes = ref<any[]>([])
const error = ref('')
const loading = ref(false)
const loadingConfig = ref(true)
const configError = ref('')

const mask = computed(() => {
  const selectedIds = new Set<string>()
  modules.value.forEach(m => {
    if (selectedModules.value.includes(m.key) && m.functionId) selectedIds.add(m.functionId)
  })
  selectedFunctions.value.forEach(id => selectedIds.add(id))
  return functionOrder.value.reduce((sum, id, index) => selectedIds.has(id) ? sum + (1 << index) : sum, 0)
})
const comboCodePreview = computed(() => mask.value
  ? `${codePrefix.value}-${String(mask.value).padStart(3, '0')}`
  : '未选择')

async function loadConfig() {
  loadingConfig.value = true
  try {
    const config: any = await api.moduleRegistry()
    modules.value = config.modules || []
    codePrefix.value = config.codePrefix || 'RB'
    functionOrder.value = config.functionOrder || config.permissionOrder || []
    modules.value.forEach((m: any) => { expanded.value[m.key] = true })
  } catch {
    configError.value = '模块注册表加载失败，请刷新后重试。'
  } finally {
    loadingConfig.value = false
  }
}

function moduleChildIds(m: any): string[] {
  return (m.children || []).map((c: any) => c.id)
}
function isModuleChecked(m: any): boolean {
  return selectedModules.value.includes(m.key)
}
function isModulePartial(m: any): boolean {
  const ids = moduleChildIds(m)
  const count = ids.filter(id => selectedFunctions.value.includes(id)).length
  return count > 0 && count < ids.length
}
function bindParentCheckbox(key: string, el: unknown) {
  parentCheckboxes[key] = (el as HTMLInputElement) || null
  nextTick(() => {
    const checkbox = parentCheckboxes[key]
    const module = modules.value.find(m => m.key === key)
    if (checkbox && module) checkbox.indeterminate = isModulePartial(module)
  })
}
function refreshIndeterminate() {
  modules.value.forEach(m => bindParentCheckbox(m.key, parentCheckboxes[m.key]))
}
function toggleModule(m: any) {
  const selected = selectedModules.value.includes(m.key)
  const childIds = moduleChildIds(m)
  if (selected) {
    selectedModules.value = selectedModules.value.filter(x => x !== m.key)
    selectedFunctions.value = selectedFunctions.value.filter(id => !childIds.includes(id))
  } else {
    selectedModules.value = [...new Set([...selectedModules.value, m.key])]
    selectedFunctions.value = [...new Set([...selectedFunctions.value, ...childIds])]
  }
  nextTick(refreshIndeterminate)
}
function toggleFunction(moduleKey: string, functionId: string) {
  const selected = selectedFunctions.value.includes(functionId)
  selectedFunctions.value = selected
    ? selectedFunctions.value.filter(id => id !== functionId)
    : [...selectedFunctions.value, functionId]
  if (!selected && !selectedModules.value.includes(moduleKey)) {
    selectedModules.value = [...selectedModules.value, moduleKey]
  }
  nextTick(refreshIndeterminate)
}

async function createOnce() {
  if (loading.value || created.value || !selectedModules.value.length) return
  const roleName = name.value.trim()
  if (!roleName) return
  loading.value = true
  error.value = ''
  try {
    created.value = await api.createRoleCombination({
      modules: [...selectedModules.value],
      functions: [...selectedFunctions.value],
      name: roleName,
    })
    renameValue.value = created.value.name
    const routes: any = await api.functionRoutes()
    generatedRoutes.value = routes.routes || []
    emit('created', created.value)
  } catch (e: any) {
    error.value = e.message || '默认角色生成失败'
  } finally {
    loading.value = false
  }
}

async function rename() {
  if (!created.value || !renameValue.value.trim()) return
  if (renameValue.value.trim() === created.value.name) return
  loading.value = true
  error.value = ''
  try {
    const updated: any = await api.updateRole(created.value.code, {
      name: renameValue.value.trim(),
      description: created.value.description || '',
    })
    created.value = { ...created.value, ...updated }
    emit('created', created.value)
  } catch (e: any) {
    error.value = e.message || '角色名称修改失败'
  } finally {
    loading.value = false
  }
}

watch(loadingConfig, async (value) => {
  if (value) return
  await nextTick()
  const firstModule = rootRef.value?.querySelector<HTMLElement>('.tree-parent input')
  firstModule?.focus()
})

onMounted(loadConfig)
</script>

<style scoped>
.combo-form { width: 100%; }
.combo-form.compact .field { margin-bottom: 10px; }
.combo-form.compact .module-option { padding: 6px 8px; }
.combo-form.compact .code-line { padding: 8px 10px; margin-bottom: 10px; }
.field { margin-bottom: 14px; }
.hint { margin: 2px 0 8px; color: var(--muted); font-size: 12px; }
.permission-tree { border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #fff; }
.tree-group + .tree-group { margin-top: 6px; border-top: 1px dashed var(--line); padding-top: 6px; }
.tree-parent, .tree-child { display: flex; align-items: center; gap: 8px; padding: 6px 4px; font-size: 12px; }
.tree-parent input, .tree-child input { width: auto; }
.tree-parent b { font-size: 13px; }
.tree-parent small, .tree-child small, .tree-child em { color: var(--muted); font-size: 11px; font-style: normal; }
.tree-parent small { margin-left: auto; }
.tree-twisty { border: 0; background: transparent; color: var(--muted); cursor: pointer; width: 16px; }
.count { color: var(--muted); font-size: 11px; }
.tree-children { padding-left: 24px; }
.tree-child { cursor: pointer; }
.tree-child em { margin-left: auto; }
.tree-empty { color: var(--muted); font-size: 11px; padding: 4px 0 6px; }
.code-line { border: 1px solid var(--tech-blue-line); background: var(--tech-blue-soft); border-radius: 8px; padding: 10px 12px; font-size: 13px; margin-bottom: 12px; }
.code-line small { display: block; color: var(--muted); font-size: 11px; margin-top: 4px; }
input { width: 100%; height: 38px; border: 1px solid var(--line); border-radius: 7px; padding: 0 10px; background: var(--white); color: var(--ink); }
.created-panel { border-top: 1px solid var(--line); margin-top: 12px; padding-top: 12px; }
.rename-row { margin: 10px 0; }
.module-fields { border: 1px solid var(--line); border-radius: 7px; padding: 8px 10px; margin: 8px 0; }
.module-fields > b { display: block; font-size: 12px; margin-bottom: 6px; }
.field-row { display: grid; gap: 2px; padding: 5px 0; border-top: 1px dashed var(--line); font-size: 12px; }
.field-row:first-of-type { border-top: 0; }
.field-row small { color: var(--muted); font-size: 10px; word-break: break-all; }
.field-row em { color: var(--muted); font-size: 11px; font-style: normal; }
.created-children { display: flex; gap: 8px; flex-wrap: wrap; color: var(--muted); font-size: 10px; margin-top: 3px; }
.created-children .on { color: var(--tech-blue); font-weight: 600; }
.msg { padding: 8px 10px; margin: 6px 0; border-radius: 6px; font-size: 12px; }
.form-foot { display: flex; margin-top: 14px; }
@media (max-width: 768px) { .tree-children { padding-left: 12px; } .tree-parent small { margin-left: 0; } }
</style>
