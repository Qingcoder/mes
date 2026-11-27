<template>
  <section class="card resource-panel">
    <div class="panel-head">
      <div>
        <h3>共享资料库</h3>
        <p class="sub">统一查看、下载与检索共享资料；资料可关联人员、产品、设备与工艺，进入页面自动拉取最新资料。</p>
      </div>
      <div class="row">
        <button class="btn sm" type="button" :disabled="loading" @click="reload">刷新</button>
      </div>
    </div>

    <div class="tabs">
      <button :class="{ active: tab === 'resources' }" type="button" @click="tab = 'resources'">共享资料库</button>
      <button :class="{ active: tab === 'overview' }" type="button" @click="tab = 'overview'">模块总览</button>
    </div>

    <div v-if="error" class="msg err">{{ error }}</div>

    <template v-if="tab === 'overview'">
      <div v-if="loading" class="empty">加载总览…</div>
      <div v-else class="overview-grid">
        <article v-for="item in modules" :key="item.key" class="overview-card">
          <div class="overview-head">
            <b>{{ item.label }}</b>
            <small class="mono">{{ item.key }}</small>
          </div>
          <div class="stats">
            <div v-for="stat in item.counts" :key="stat.label">
              <span>{{ stat.label }}</span>
              <b>{{ stat.value }}</b>
            </div>
          </div>
          <div class="overview-foot">
            <span class="mini mono">{{ item.permission }}</span>
            <router-link class="link" :to="item.route">打开模块</router-link>
          </div>
        </article>
      </div>
    </template>

    <template v-else>
      <div class="readonly-note">
        当前为<b>只读</b>查看：可查看、下载、检索与查看版本记录；上传与编辑入口迁移中，暂不可用。
      </div>

      <div class="toolbar">
        <label>模块
          <select v-model="filters.module" @change="loadResources">
            <option value="">全部模块</option>
            <option v-for="item in moduleOptions" :key="item.key" :value="item.key">{{ item.label }}</option>
          </select>
        </label>
        <label>类别
          <select v-model="filters.category" @change="loadResources">
            <option value="">全部类别</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label>关键词<input v-model="filters.q" placeholder="标题 / 文件名 / 说明" @keyup.enter="loadResources" /></label>
        <button class="btn" type="button" @click="loadResources">查询</button>
      </div>

      <div class="table-scroll">
        <table>
          <thead><tr><th>标题</th><th>关联对象</th><th>文件</th><th>版本</th><th>大小</th><th>上传人</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in resources" :key="row.id">
              <td>
                <b>{{ row.title }}</b>
                <p v-if="row.description" class="desc">{{ row.description }}</p>
              </td>
              <td class="relations">{{ relationText(row) || '—' }}</td>
              <td class="mono">{{ row.fileName }}</td>
              <td>v{{ row.version || 1 }}</td>
              <td>{{ formatSize(row.size) }}</td>
              <td>{{ row.uploadedBy || '—' }}</td>
              <td>{{ formatTime(row.updatedAt || row.uploadedAt) }}</td>
              <td>
                <button class="link" type="button" @click="view(row)">查看</button>
                <button class="link" type="button" @click="download(row)">下载</button>
                <button class="link" type="button" @click="openHistory(row)">历史</button>
              </td>
            </tr>
            <tr v-if="!resources.length"><td colspan="8" class="empty">暂无资料</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-if="historyOpen" class="modal-mask" @click.self="historyOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <div class="panel-head"><b>版本记录：{{ historyTitle }}</b><button class="btn sm" type="button" @click="historyOpen = false">关闭</button></div>
        <div v-if="!historyRows.length" class="empty">暂无版本记录</div>
        <div v-for="item in historyRows" :key="item.version + item.at" class="history-row">
          <b>v{{ item.version }}</b>
          <span>{{ item.action === 'upload' ? '上传' : '更新' }}</span>
          <span>{{ item.by || '—' }}</span>
          <span>{{ formatTime(item.at) }}</span>
          <p>{{ item.note || '—' }}</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api'

const tab = ref<'overview' | 'resources'>('resources')
const loading = ref(false)
const historyOpen = ref(false)
const historyRows = ref<any[]>([])
const historyTitle = ref('')
const error = ref('')
const modules = ref<any[]>([])
const resources = ref<any[]>([])
const filters = reactive<any>({ module: '', category: '', q: '' })
const categories = ['制度文件', '作业指导', '图纸规范', '检验报告', '设备资料', '培训资料', '会议纪要', '其他']
const defaultModules = [
  { key: 'dashboard', label: '看板' }, { key: 'person', label: '人员管理' },
  { key: 'machine', label: '设备管理' }, { key: 'material', label: '物料管理' },
  { key: 'method', label: '工艺管理' }, { key: 'environment', label: '共享资料库' },
  { key: 'wo', label: '工单管理' }, { key: 'station', label: '站点作业' },
  { key: 'pack', label: '包装管理' }, { key: 'query', label: '数据查询' },
  { key: 'quality', label: '质量控制' }, { key: 'account', label: '账户权限' },
]
const moduleOptions = computed(() => modules.value.length ? modules.value : defaultModules)

function moduleLabel(key: string) {
  return moduleOptions.value.find(m => m.key === key)?.label || key
}
function relationText(row: any) {
  const fields = ['relatedPersons', 'relatedProducts', 'relatedEquipment', 'relatedStations']
  return fields.flatMap(field => (row?.[field] || []).map((item: any) => item.name || item.code)).join('、')
}
function formatSize(size: number) {
  const n = Number(size) || 0
  return n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)}MB` : `${Math.max(1, Math.round(n / 1024))}KB`
}
function formatTime(value: string) {
  if (!value) return '—'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('zh-CN', { hour12: false })
}
async function reload() {
  loading.value = true
  error.value = ''
  try {
    const overview = await api.environmentOverview()
    modules.value = overview.modules || []
    await loadResources()
  } catch (e: any) {
    error.value = e.message || '环境总览加载失败'
  } finally {
    loading.value = false
  }
}
async function loadResources() {
  try {
    resources.value = await api.environmentResources({ ...filters })
  } catch (e: any) {
    error.value = e.message || '资料列表加载失败'
  }
}
async function openFile(blob: Blob, fileName: string, view: boolean) {
  const url = URL.createObjectURL(blob)
  if (view) {
    window.open(url, '_blank', 'noopener')
  } else {
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    link.click()
  }
  setTimeout(() => URL.revokeObjectURL(url), 30000)
}
async function view(row: any) {
  try { openFile(await api.downloadEnvironmentResource(row.id), row.fileName, true) }
  catch (e: any) { error.value = e.message || '资料查看失败' }
}
async function download(row: any) {
  try { openFile(await api.downloadEnvironmentResource(row.id), row.fileName, false) }
  catch (e: any) { error.value = e.message || '资料下载失败' }
}
function openHistory(row: any) {
  historyTitle.value = row.title || row.fileName || ''
  historyRows.value = [...(row.history || [])].reverse()
  historyOpen.value = true
}

onMounted(reload)
</script>

<style scoped>
.resource-panel { margin-bottom: 12px; }
.readonly-note {
  border: 1px solid var(--tech-blue-line);
  background: var(--tech-blue-soft);
  color: var(--ink);
  border-radius: 7px;
  padding: 9px 12px;
  font-size: 12px;
  margin-bottom: 10px;
}
.readonly-note b { color: var(--tech-blue); }
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
h3 { font-size: 16px; }
.sub, .mini, .desc { color: var(--muted); }
.sub { font-size: 12px; margin-top: 4px; }
.mini { font-size: 11px; }
.desc { font-size: 11px; margin: 3px 0 0; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
.tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--line); padding-bottom: 8px; margin: 12px 0; }
.tabs button { border: 1px solid var(--line); background: var(--white); color: var(--ink); border-radius: 6px; padding: 6px 12px; cursor: pointer; font-family: inherit; }
.tabs button.active { border-color: var(--tech-blue); background: var(--tech-blue-soft); color: var(--tech-blue); }
.overview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
.overview-card { border: 1px solid var(--line); border-radius: 8px; padding: 10px; }
.overview-head { display: flex; justify-content: space-between; align-items: center; }
.overview-head small { color: var(--muted); font-size: 10px; }
.stats { display: grid; gap: 5px; margin: 9px 0; }
.stats > div { display: flex; justify-content: space-between; border-bottom: 1px dashed var(--line); padding: 4px 0; font-size: 12px; }
.stats span { color: var(--muted); }
.overview-foot { display: flex; justify-content: space-between; align-items: center; }
.upload-box { border: 1px dashed var(--line); border-radius: 8px; padding: 10px; margin-bottom: 10px; }
.upload-box.active { border-color: var(--tech-blue); background: var(--tech-blue-soft); }
.upload-title { font-weight: 700; font-size: 13px; margin-bottom: 8px; }
.native-file-input { display: none !important; }
.selected-files { margin: 6px 0; color: var(--muted); font-size: 11px; overflow-wrap: anywhere; }
.upload-form { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 8px; align-items: end; }
.upload-form label, .toolbar label, .relation-grid label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.relation-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 8px; margin: 10px 0; }
.relation-grid select { min-height: 72px; }
.file-label { grid-column: 2 / -1; }
.relations { color: var(--muted); font-size: 11px; max-width: 260px; }
.history-row { display: grid; grid-template-columns: 40px 60px 100px 150px 1fr; gap: 8px; align-items: center; border-bottom: 1px dashed var(--line); padding: 7px 0; font-size: 11px; }
.history-row p { margin: 0; color: var(--muted); }
.toolbar { display: flex; gap: 10px; align-items: end; flex-wrap: wrap; margin: 10px 0; }
.toolbar label { min-width: 180px; }
input, select { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 7px 8px; font-family: inherit; color: var(--ink); background: var(--white); }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
.link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; padding: 0 6px 0 0; font-family: inherit; font-size: 11px; }
.danger-link { color: var(--red); }
.empty { text-align: center; color: var(--muted); padding: 14px; }
.msg { padding: 9px 12px; border-radius: 5px; margin-bottom: 10px; }
.msg.err { background: var(--red-soft); color: var(--red); }
.msg.ok { background: var(--green-soft); color: var(--green); }
.modal-mask { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(4,8,18,.65); }
.modal { width: 100%; max-width: 620px; background: var(--white); border-radius: 10px; padding: 18px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; margin-top: 12px; }
.form-grid label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
@media (max-width: 800px) { .panel-head { flex-direction: column; } .upload-form, .relation-grid, .form-grid { grid-template-columns: 1fr; } .history-row { grid-template-columns: 36px 50px 1fr; } .file-label { grid-column: auto; } }
</style>
