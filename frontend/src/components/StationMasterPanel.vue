<template>
  <section class="card station-master">
    <div class="panel-head">
      <div class="head-copy">
        <label class="library-name">库名称<input v-model="libraryNameDraft" :disabled="!canManage" placeholder="请输入库名称" @input="markDirty" /></label>
        <p class="sub">维护站点编码、名称、类型与说明；保存后按编码同步到工艺设计，设计页修改这些字段后也会同步到这里，不清空参数与附件。</p>
      </div>
      <div class="row">
        <button class="btn sm" type="button" :disabled="saving" @click="load">刷新</button>
        <button class="btn sm primary" type="button" :disabled="!dirty || saving || !canManage" @click="save">保存主数据</button>
      </div>
    </div>

    <div v-if="error" class="msg err">{{ error }}</div>
    <div v-if="notice" class="msg ok">{{ notice }}</div>
    <div v-if="!canManage" class="msg">当前账号无 `method:manage` 权限，仅可查看主数据。</div>

    <div class="tabs">
      <button :class="{ active: tab === 'library' }" type="button" @click="tab = 'library'">站点库</button>
      <button :class="{ active: tab === 'types' }" type="button" @click="tab = 'types'">站点类型</button>
      <button :class="{ active: tab === 'groups' }" type="button" @click="tab = 'groups'">站点分组</button>
      <router-link class="btn sm" to="/method">返回工艺管理选择编码</router-link>
    </div>

    <div v-if="loading" class="empty">加载主数据…</div>
    <template v-else-if="master">
      <div v-if="tab === 'library'" class="master-layout">
        <aside class="tree">
          <div class="tree-title">库分组</div>
          <button
            v-for="group in sortedLibraryGroups"
            :key="group.id"
            class="tree-row"
            :class="{ active: group.id === selectedGroupId }"
            type="button"
            @click="selectGroup(group.id)"
          >
            <b>{{ group.name }}</b>
            <small class="mono">{{ group.prefix }}</small>
            <span>{{ (group.items || []).length }}</span>
          </button>
          <div v-if="!sortedLibraryGroups.length" class="empty">暂无库分组</div>
          <div class="tree-add">
            <input v-model="newLibraryGroup.name" placeholder="分组名称" :disabled="!canManage" />
            <input v-model="newLibraryGroup.prefix" placeholder="前缀" maxlength="8" :disabled="!canManage" />
            <input v-model.number="newLibraryGroup.start" type="number" min="1" title="起始序号" :disabled="!canManage" />
            <input v-model.number="newLibraryGroup.step" type="number" min="1" title="步长" :disabled="!canManage" />
            <button class="btn sm" type="button" :disabled="!canManage" @click="addLibraryGroup">新增分组</button>
          </div>
        </aside>

        <div v-if="activeGroup" class="editor">
          <div class="editor-head">
            <div>
              <b>{{ activeGroup.name }}</b>
              <small class="mono">{{ activeGroup.prefix }}</small>
            </div>
            <button class="btn sm danger" type="button" :disabled="!canManage || (activeGroup.items || []).length > 0" @click="removeLibraryGroup">删除分组</button>
          </div>
          <div class="form-grid">
            <label>分组名称<input v-model="activeGroup.name" :disabled="!canManage" @input="markDirty" /></label>
            <label>编码前缀<input v-model="activeGroup.prefix" maxlength="8" :disabled="!canManage" @input="markDirty" /></label>
            <label>起始序号<input v-model.number="activeGroup.start" type="number" min="1" :disabled="!canManage" @input="markDirty" /></label>
            <label>递增长度<input v-model.number="activeGroup.step" type="number" min="1" :disabled="!canManage" @input="markDirty" /></label>
            <label class="full">说明<input v-model="activeGroup.description" :disabled="!canManage" @input="markDirty" /></label>
          </div>

          <div class="section-head">
            <b>库项</b>
            <button class="btn sm" type="button" :disabled="!canManage" @click="addLibraryItem">新增库项</button>
          </div>
          <div class="table-scroll">
            <table>
              <thead><tr><th>编码</th><th>名称</th><th>类型</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="item in activeGroup.items || []" :key="item.id" :class="{ active: item.id === selectedItemId }" @click="selectedItemId = item.id">
                  <td class="mono">{{ item.code }}</td>
                  <td><input v-model="item.name" :disabled="!canManage" @input="markDirty" @click.stop /></td>
                  <td>
                    <select v-model="item.type" :disabled="!canManage" @change="markDirty" @click.stop>
                      <option v-for="type in master.stationTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
                    </select>
                  </td>
                  <td>{{ usedLibraryCodes.includes(item.code) ? '已使用' : '可用' }}</td>
                  <td>
                    <button class="link danger-link" type="button" :disabled="!canManage || usedLibraryCodes.includes(item.code)" @click.stop="removeLibraryItem(item)">删除</button>
                  </td>
                </tr>
                <tr v-if="!(activeGroup.items || []).length"><td colspan="5" class="empty">暂无库项</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-else class="empty">请选择左侧库分组</div>
      </div>

      <div v-else-if="tab === 'types'" class="simple-grid">
        <div class="form-grid">
          <label>类型名称<input v-model="newTypeLabel" placeholder="新增站点类型名称" :disabled="!canManage" /></label>
          <button class="btn" type="button" :disabled="!canManage || !newTypeLabel.trim()" @click="addType">新增类型</button>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>内部值</th><th>显示名称</th><th>引用</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="type in master.stationTypes" :key="type.value">
                <td class="mono">{{ type.value }}</td>
                <td><input v-model="type.label" :disabled="!canManage" @input="markDirty" /></td>
                <td>{{ usedTypeValues.includes(type.value) ? '已使用' : '未使用' }}</td>
                <td>
                  <button class="link danger-link" type="button" :disabled="!canManage || usedTypeValues.includes(type.value)" @click="removeType(type)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else class="simple-grid">
        <div class="form-grid">
          <label>分组名称<input v-model="newStationGroup.name" placeholder="如：主线流程" :disabled="!canManage" /></label>
          <label>说明<input v-model="newStationGroup.description" placeholder="可选" :disabled="!canManage" /></label>
          <button class="btn" type="button" :disabled="!canManage || !newStationGroup.name.trim()" @click="addStationGroup">新增分组</button>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>分组</th><th>说明</th><th>引用</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="group in sortedStationGroups" :key="group.id">
                <td><input v-model="group.name" :disabled="!canManage" @input="markDirty" /></td>
                <td><input v-model="group.description" :disabled="!canManage" @input="markDirty" /></td>
                <td>{{ usedGroupIds.includes(group.id) ? '已使用' : '未使用' }}</td>
                <td>
                  <button class="link danger-link" type="button" :disabled="!canManage || usedGroupIds.includes(group.id)" @click="removeStationGroup(group)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, getUser } from '../api'
import { sharedPerms } from '../stores/permStore'

const master = ref<any>(null)
const libraryNameDraft = ref('工位/站点主数据')
const loading = ref(false)
const saving = ref(false)
const dirty = ref(false)
const error = ref('')
const notice = ref('')
const tab = ref('library')
const selectedGroupId = ref('')
const selectedItemId = ref('')
const newTypeLabel = ref('')
const newLibraryGroup = reactive({ name: '', prefix: '', start: 10, step: 10 })
const newStationGroup = reactive({ name: '', description: '' })

const canManage = computed(() => getUser()?.role === 'admin' || sharedPerms.value.includes('method:manage'))
const sortedLibraryGroups = computed(() => [...(master.value?.library || [])].sort((a: any, b: any) => (a.order || 0) - (b.order || 0)))
const sortedStationGroups = computed(() => [...(master.value?.groups || [])].sort((a: any, b: any) => (a.order || 0) - (b.order || 0)))
const activeGroup = computed(() => sortedLibraryGroups.value.find((g: any) => g.id === selectedGroupId.value) || null)
const usedLibraryCodes = computed<string[]>(() => master.value?.usedLibraryCodes || [])
const usedTypeValues = computed<string[]>(() => master.value?.usedTypeValues || [])
const usedGroupIds = computed<string[]>(() => master.value?.usedGroupIds || [])

function newId(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1000)}`
}
function markDirty() {
  dirty.value = true
  notice.value = ''
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    master.value = await api.processDesignMaster()
    libraryNameDraft.value = master.value.libraryName || '工位/站点主数据'
    selectedGroupId.value = sortedLibraryGroups.value[0]?.id || ''
    selectedItemId.value = ''
    dirty.value = false
  } catch (e: any) {
    error.value = e.message || '主数据加载失败'
  } finally {
    loading.value = false
  }
}
async function save() {
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const libraryName = String(libraryNameDraft.value || '').trim()
    if (!libraryName) { error.value = '库名称不能为空'; return }
    master.value = await api.saveProcessDesignMaster({
      groups: master.value.groups,
      library: master.value.library,
      stationTypes: master.value.stationTypes,
      libraryName,
    })
    libraryNameDraft.value = master.value.libraryName || libraryName
    selectedGroupId.value = sortedLibraryGroups.value.find((g: any) => g.id === selectedGroupId.value)?.id || sortedLibraryGroups.value[0]?.id || ''
    dirty.value = false
    notice.value = '主数据已保存'
  } catch (e: any) {
    error.value = e.message || '主数据保存失败'
  } finally {
    saving.value = false
  }
}
function selectGroup(id: string) {
  selectedGroupId.value = id
  selectedItemId.value = ''
}
function allLibraryCodes() {
  return sortedLibraryGroups.value.flatMap((g: any) => (g.items || []).map((i: any) => String(i.code || '').toUpperCase()))
}
function nextLibraryCode(group: any) {
  const prefix = String(group.prefix || '').toUpperCase().replace(/[^A-Z0-9]/g, '') || 'OP'
  const step = Math.max(1, Number(group.step) || 10)
  const used = new Set(allLibraryCodes())
  const nums = (group.items || [])
    .map((item: any) => new RegExp(`^${prefix}(\\d+)$`).exec(String(item.code || '').toUpperCase()))
    .filter(Boolean)
    .map((match: RegExpExecArray | null) => Number(match![1]))
  let next = nums.length ? Math.max(...nums) + step : (Number(group.start) || step)
  while (used.has(`${prefix}${next}`)) next += step
  return `${prefix}${next}`
}
function addLibraryGroup() {
  const name = newLibraryGroup.name.trim()
  const prefix = String(newLibraryGroup.prefix || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
  if (!name || !prefix) { error.value = '请填写库分组名称和编码前缀'; return }
  if (sortedLibraryGroups.value.some((g: any) => String(g.prefix).toUpperCase() === prefix)) {
    error.value = '编码前缀已存在'; return
  }
  const group = {
    id: newId('lib_grp'), name, prefix,
    start: Math.max(1, Number(newLibraryGroup.start) || 1),
    step: Math.max(1, Number(newLibraryGroup.step) || 10),
    description: '', order: sortedLibraryGroups.value.length + 1, items: [],
  }
  master.value.library.push(group)
  selectedGroupId.value = group.id
  newLibraryGroup.name = ''
  newLibraryGroup.prefix = ''
  newLibraryGroup.start = 10
  newLibraryGroup.step = 10
  error.value = ''
  markDirty()
}
function removeLibraryGroup() {
  const group = activeGroup.value
  if (!group) return
  if ((group.items || []).length) { error.value = '请先删除该分组下的库项'; return }
  master.value.library = master.value.library.filter((g: any) => g.id !== group.id)
  selectedGroupId.value = sortedLibraryGroups.value[0]?.id || ''
  error.value = ''
  markDirty()
}
function addLibraryItem() {
  if (!activeGroup.value) return
  const code = nextLibraryCode(activeGroup.value)
  const item = { id: newId('lib'), code, name: String(activeGroup.value.prefix) + code.slice(String(activeGroup.value.prefix).length), type: master.value.stationTypes[0]?.value || '', description: '' }
  activeGroup.value.items = [...(activeGroup.value.items || []), item]
  selectedItemId.value = item.id
  error.value = ''
  markDirty()
}
function removeLibraryItem(item: any) {
  if (!activeGroup.value || usedLibraryCodes.value.includes(item.code)) {
    error.value = '该库编码已被站点使用，不能删除'
    return
  }
  activeGroup.value.items = (activeGroup.value.items || []).filter((i: any) => i.id !== item.id)
  if (selectedItemId.value === item.id) selectedItemId.value = ''
  error.value = ''
  markDirty()
}
function addType() {
  const label = newTypeLabel.value.trim()
  if (!label) return
  master.value.stationTypes.push({ value: `type_${Date.now()}`, label })
  newTypeLabel.value = ''
  error.value = ''
  markDirty()
}
function removeType(type: any) {
  if (usedTypeValues.value.includes(type.value)) {
    error.value = `类型“${type.label}”已被站点或库项使用，不能删除`
    return
  }
  master.value.stationTypes = master.value.stationTypes.filter((t: any) => t.value !== type.value)
  error.value = ''
  markDirty()
}
function addStationGroup() {
  const name = newStationGroup.name.trim()
  if (!name) return
  const group = { id: newId('grp'), name, description: newStationGroup.description.trim(), order: sortedStationGroups.value.length + 1 }
  master.value.groups.push(group)
  newStationGroup.name = ''
  newStationGroup.description = ''
  error.value = ''
  markDirty()
}
function removeStationGroup(group: any) {
  if (usedGroupIds.value.includes(group.id)) {
    error.value = '该分组已被站点使用，不能删除'
    return
  }
  master.value.groups = master.value.groups.filter((g: any) => g.id !== group.id)
  error.value = ''
  markDirty()
}

onMounted(load)
</script>

<style scoped>
.station-master { margin-bottom: 12px; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.head-copy { flex: 1; min-width: 0; }
.library-name { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.library-name input { max-width: 320px; font-size: 16px; font-weight: 700; }
h3 { font-size: 16px; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
.tabs { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; border-bottom: 1px solid var(--line); padding-bottom: 8px; margin: 12px 0; }
.tabs button { border: 1px solid var(--line); background: var(--white); color: var(--ink); border-radius: 6px; padding: 6px 12px; cursor: pointer; font-family: inherit; }
.tabs button.active { border-color: var(--tech-blue); background: var(--tech-blue-soft); color: var(--tech-blue); }
.master-layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 12px; }
.tree { border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
.tree-title { color: var(--muted); font-size: 12px; padding: 4px 6px 8px; }
.tree-row { display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: 6px; width: 100%; border: 0; background: transparent; border-radius: 6px; padding: 7px; text-align: left; cursor: pointer; font-family: inherit; color: var(--ink); align-items: center; }
.tree-row.active, .tree-row:hover { background: var(--tech-blue-soft); }
.tree-row small { color: var(--muted); }
.tree-row span { color: var(--tech-blue); font-size: 11px; }
.tree-add, .form-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 6px; margin-top: 8px; }
.tree-add { grid-template-columns: 1fr 70px 64px 64px; }
.tree-add .btn { grid-column: 1 / -1; }
.form-grid label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.full { grid-column: 1 / -1; }
input, select { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 7px 8px; font-family: inherit; color: var(--ink); background: var(--white); }
.editor { border: 1px solid var(--line); border-radius: 8px; padding: 10px; min-width: 0; }
.editor-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.editor-head small { margin-left: 8px; color: var(--muted); }
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 12px 0 6px; font-size: 13px; }
.simple-grid { display: grid; gap: 10px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid var(--line); padding: 7px; text-align: left; }
th { color: var(--muted); font-weight: 600; }
td input, td select { padding: 5px 6px; }
.link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; padding: 0; font-family: inherit; font-size: 11px; }
.link:disabled { color: var(--muted); cursor: not-allowed; }
.danger-link { color: var(--red); }
.empty { color: var(--muted); padding: 12px; text-align: center; }
.msg { padding: 9px 12px; border-radius: 5px; margin-bottom: 10px; }
.msg.err { background: var(--red-soft); color: var(--red); }
.msg.ok { background: var(--green-soft); color: var(--green); }
@media (max-width: 900px) { .master-layout { grid-template-columns: 1fr; } .tree-add { grid-template-columns: 1fr 1fr; } }
@media (max-width: 600px) { .panel-head { flex-direction: column; } .form-grid { grid-template-columns: 1fr; } .full { grid-column: auto; } }
</style>
