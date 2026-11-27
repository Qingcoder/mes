<template>
  <div class="product-page">
    <div class="head">
      <div>
        <h2>产品资料</h2>
        <p class="sub">先由你命名产品，再导入 SN；系统不会根据文件名或 SN 自动识别版本。</p>
      </div>
      <div class="row">
        <router-link class="btn" to="/wo">返回工单管理</router-link>
        <button class="btn" type="button" :disabled="!selectedCode || !allRows.length" @click="exportSn">导出 SN</button>
        <button v-if="canManage" class="btn primary" type="button" @click="createProduct">新增产品</button>
      </div>
    </div>

    <div v-if="error" class="msg err">{{ error }}</div>
    <div v-if="notice" class="msg ok">{{ notice }}</div>
    <div v-if="loading" class="msg">加载产品资料…</div>

    <div class="product-layout">
      <aside class="card product-list">
        <div class="panel-head"><b>产品列表</b><span class="mini">{{ profiles.length }} 个</span></div>
        <button
          v-for="item in profiles"
          :key="item.code"
          class="product-item"
          :class="{ active: item.code === selectedCode }"
          type="button"
          @click="selectProduct(item.code)"
        >
          <b>{{ item.name }}</b>
          <small class="mono">{{ item.code }}</small>
        </button>
        <div v-if="!profiles.length" class="empty">暂无产品，点击“新增产品”创建</div>
      </aside>

      <main class="product-main">
        <section class="card">
          <div class="panel-head"><b>产品名称</b><span class="mini mono">{{ selectedCode || '未选择' }}</span></div>
          <template v-if="product">
            <div class="name-row">
              <input v-model="nameDraft" :disabled="!canManage" placeholder="请输入产品名称" @keyup.enter="saveName" />
              <button v-if="canManage" class="btn primary" type="button" @click="saveName">保存名称</button>
            </div>
            <p class="mini">产品名称由你填写；系统只生成编码和 SN 清单结构，不会自动判断版本。</p>
          </template>
          <div v-else class="empty">请先新增或选择产品</div>
        </section>

        <section v-if="product" class="card">
          <div class="panel-head"><b>导入 SN</b><button class="btn sm" type="button" @click="downloadTemplate">下载模板</button></div>
          <p class="mini">当前产品：{{ product.name }}。SN 只会导入到这个产品，不会自动切换到其他版本。</p>
          <div class="import-grid">
            <div class="single-add-row">
              <input v-model="singleSn" class="mono" placeholder="输入单个 SN 后点添加" @keyup.enter="addSingleSn" />
              <button class="btn sm" type="button" :disabled="!canManage || !singleSn.trim()" @click="addSingleSn">添加单个</button>
            </div>
            <label class="full-line">
              <span>批量添加 SN（每行一个，也支持逗号/空格分隔）</span>
              <textarea v-model="snText" rows="6" class="mono" placeholder="DAGZ2226BP00016A"></textarea>
            </label>
            <div class="full-line">
              <span class="drop-label">或拖拽文件到这里（.xlsx / .xls / .csv / .txt）</span>
              <div
                class="sn-drop-zone"
                :class="{ active: snDragging }"
                @click="fileInput?.click()"
                @dragover.prevent="snDragging = true"
                @dragenter.prevent="snDragging = true"
                @dragleave.prevent="snDragging = false"
                @drop.prevent="onSnDrop"
              >
                {{ selectedSnFiles.length ? selectedSnFiles.map(f => f.name).join('、') : '点击选择文件，或拖拽多个文件到这里' }}
              </div>
              <input ref="fileInput" class="native-file-input" type="file" accept=".xlsx,.xls,.csv,.txt" multiple @change="onFileChange" />
            </div>
          </div>
          <div v-if="importResult" class="msg ok">
            成功 {{ importResult.createdCount }} 个，跳过 {{ importResult.skippedCount }} 个。
          </div>
          <div v-if="importResult?.skipped?.length" class="skip-list">
            <div v-for="(item, index) in importResult.skipped.slice(0, 10)" :key="index" class="skip-row">
              <span class="mono">{{ item.sn || '空值' }}</span><span>{{ item.reason }}</span>
            </div>
          </div>
          <div class="import-actions">
            <button class="btn primary" type="button" :disabled="!canManage || !selectedCode || importing" @click="importSns">
              {{ importing ? '导入中…' : '导入 SN' }}
            </button>
            <button class="btn" type="button" :disabled="!snText && !selectedSnFiles.length" @click="clearImport">清空</button>
          </div>
        </section>

        <section class="card">
          <div class="panel-head">
            <b>SN 清单</b>
            <span class="mini">共 {{ allRows.length }} 个</span>
          </div>
          <div class="toolbar inline">
            <input v-model="snFilter" class="mono" placeholder="筛选 SN" />
            <span class="mini">显示 {{ filteredRows.length }} 个</span>
          </div>
          <div class="table-scroll">
            <table>
              <thead><tr><th>选择</th><th>序号</th><th>SN</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="(row, index) in pagedRows" :key="row.sn">
                  <td><input v-if="canManage" type="checkbox" :checked="selectedSns.includes(row.sn)" @change="toggleSn(row.sn)" /></td>
                  <td>{{ (page - 1) * pageSize + index + 1 }}</td>
                  <td class="mono">{{ row.sn }}</td>
                  <td class="ops">
                    <button class="link" type="button" @click="copySn(row.sn)">复制</button>
                  </td>
                </tr>
                <tr v-if="!pagedRows.length"><td colspan="4" class="empty">暂无 SN</td></tr>
              </tbody>
            </table>
          </div>
          <div class="pager">
            <button class="btn sm" :disabled="page <= 1" @click="page -= 1">上一页</button>
            <span class="mini">{{ page }} / {{ totalPages }}</span>
            <button class="btn sm" :disabled="page >= totalPages" @click="page += 1">下一页</button>
          </div>
        </section>

        <section v-if="product && canManage" class="card delete-sn-card">
          <div class="panel-head"><b>删除 SN</b><span class="mini">独立操作区</span></div>
          <p class="mini">当前产品：{{ product.name }}（{{ selectedCode }}）。先在上方 SN 清单勾选，再在这里删除。</p>
          <div class="delete-sn-bar">
            <span class="selected-count">已选 <b>{{ selectedSns.length }}</b> 个</span>
            <button class="btn sm" type="button" :disabled="!filteredRows.length" @click="selectAllFiltered">全选当前结果</button>
            <button class="btn sm" type="button" :disabled="!filteredRows.length" @click="selectCurrentPage">全选本页</button>
            <button class="btn sm" type="button" :disabled="!selectedSns.length" @click="selectedSns = []">清空选择</button>
            <button class="btn sm danger" type="button" :disabled="!selectedSns.length" @click="removeSelectedSns">删除所选（{{ selectedSns.length }}）</button>
          </div>
        </section>
      </main>
    </div>

    <div v-if="createOpen" class="modal-mask" @click.self="createOpen = false">
      <div class="modal small" role="dialog" aria-modal="true">
        <div class="panel-head"><b>新增产品</b><button class="btn sm" type="button" @click="createOpen = false">关闭</button></div>
        <div v-if="formError" class="msg err">{{ formError }}</div>
        <p class="sub">请按这批 SN 的实际版本自行命名；系统不会从文件名推断版本。</p>
        <label>产品名称<input v-model="newName" autofocus placeholder="如：V2.5 无本体数采夹爪" @keyup.enter="saveProduct" /></label>
        <div class="modal-foot">
          <button class="btn" type="button" @click="createOpen = false">取消</button>
          <button class="btn primary" type="button" @click="saveProduct">创建产品</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, friendlyError, getUser } from '../api'
import { sharedPerms } from '../stores/permStore'
import { useProductProfiles } from '../composables/useProductProfiles'
import { dedupe, downloadSnTemplate, normalizeSns, parseSnFile } from '../utils/import'

const route = useRoute()
const selectedCode = ref('')
const product = ref<any>(null)
const nameDraft = ref('')
const snText = ref('')
const singleSn = ref('')
const snDragging = ref(false)
const selectedSnFiles = ref<File[]>([])
const snFilter = ref('')
const selectedSns = ref<string[]>([])
const page = ref(1)
const pageSize = 20
const formError = ref('')
const createOpen = ref(false)
const newName = ref('')
const importing = ref(false)
const importResult = ref<any>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const canManage = computed(() => getUser()?.role === 'admin' || sharedPerms.value.some(p => ['wo:create', 'material:manage'].includes(p)))

// 产品主数据（新增/改名/列表）复用共享逻辑，与「产品主数据」面板保持同一套行为。
const { profiles, loading, error, notice, load: loadProductList, create: createProfile, rename: renameProfile } = useProductProfiles()

const allRows = computed(() => product.value?.snRows || [])
const filteredRows = computed(() => {
  const q = snFilter.value.trim().toUpperCase()
  return allRows.value.filter((row: any) => !q || String(row.sn).toUpperCase().includes(q))
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize)))
const pagedRows = computed(() => filteredRows.value.slice((page.value - 1) * pageSize, page.value * pageSize))

async function loadProfiles() {
  const list = await loadProductList()
  const wanted = String(route.query.product || route.query.code || '')
  const target = wanted ? list.find((p: any) => [p.code, p.name].includes(wanted)) : null
  if (target) await selectProduct(target.code)
  else { selectedCode.value = ''; product.value = null; nameDraft.value = '' }
}
async function selectProduct(code: string) {
  error.value = ''
  selectedCode.value = code
  nameDraft.value = ''
  importResult.value = null
  selectedSns.value = []
  page.value = 1
  snFilter.value = ''
  try {
    product.value = await api.productProfile(code)
    nameDraft.value = product.value?.name || ''
  } catch (e: any) {
    error.value = friendlyError(e, '产品资料加载失败')
    product.value = null
  }
}
function createProduct() {
  formError.value = ''
  newName.value = ''
  createOpen.value = true
}
async function saveProduct() {
  formError.value = ''
  const name = String(newName.value || '').trim()
  if (!name) { formError.value = '请输入产品名称'; return }
  const created = await createProfile(name)
  if (!created) { formError.value = error.value || '产品创建失败'; return }
  createOpen.value = false
  await loadProfiles()
  await selectProduct(created.code)
}
async function saveName() {
  if (!selectedCode.value) return
  const ok = await renameProfile(selectedCode.value, nameDraft.value)
  if (!ok) return
  await loadProfiles()
  await selectProduct(selectedCode.value)
}
function clearImport() {
  snText.value = ''
  singleSn.value = ''
  selectedSnFiles.value = []
  importResult.value = null
  if (fileInput.value) fileInput.value.value = ''
}
function addSingleSn() {
  const value = String(singleSn.value || '').trim().toUpperCase()
  if (!value) return
  const current = normalizeSns(snText.value)
  snText.value = dedupe([...current, value]).join('\n')
  singleSn.value = ''
  error.value = ''
}
function onSnDrop(event: DragEvent) {
  snDragging.value = false
  const files = Array.from(event.dataTransfer?.files || [])
  if (files.length) void loadSnFiles(files)
}
async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (files.length) await loadSnFiles(files)
}
async function loadSnFiles(files: File[]) {
  const values = normalizeSns(snText.value)
  const loaded: File[] = []
  const errors: string[] = []
  for (const file of files) {
    const parsed = await parseSnFile(file)
    if (parsed.errorMessage) { errors.push(`${file.name}：${parsed.errorMessage}`); continue }
    loaded.push(file)
    values.push(...parsed.values)
  }
  selectedSnFiles.value = loaded
  snText.value = dedupe(values).join('\n')
  error.value = errors.join('；')
}
async function importSns() {
  if (!selectedCode.value) return
  const values = dedupe(normalizeSns(snText.value))
  if (!values.length) { error.value = '请填写或选择 SN'; return }
  importing.value = true
  error.value = ''
  importResult.value = null
  try {
    const result = await api.importProductSns(selectedCode.value, values)
    importResult.value = result
    notice.value = `成功导入 ${result.createdCount} 个 SN`
    await selectProduct(selectedCode.value)
  } catch (e: any) {
    error.value = friendlyError(e, 'SN 导入失败')
  } finally {
    importing.value = false
  }
}
function toggleSn(sn: string) {
  selectedSns.value = selectedSns.value.includes(sn)
    ? selectedSns.value.filter(item => item !== sn)
    : [...selectedSns.value, sn]
}
function selectCurrentPage() {
  const current = pagedRows.value.map((row: any) => row.sn)
  const allSelected = current.every((sn: string) => selectedSns.value.includes(sn))
  selectedSns.value = allSelected
    ? selectedSns.value.filter(sn => !current.includes(sn))
    : Array.from(new Set([...selectedSns.value, ...current]))
}
function selectAllFiltered() {
  selectedSns.value = filteredRows.value.map((row: any) => row.sn)
}
async function removeSelectedSns() {
  if (!selectedCode.value || !selectedSns.value.length) return
  if (!window.confirm(`确认批量删除选中的 ${selectedSns.value.length} 个 SN？`)) return
  error.value = ''
  try {
    const result: any = await api.deleteProductSns(selectedCode.value, selectedSns.value)
    selectedSns.value = []
    await selectProduct(selectedCode.value)
    notice.value = `已删除 ${result.removedCount || 0} 个 SN${result.missing?.length ? `，${result.missing.length} 个未找到` : ''}`
  } catch (e: any) {
    error.value = friendlyError(e, '批量删除失败')
  }
}
async function removeSn(sn: string) {
  if (!selectedCode.value || !window.confirm(`确认删除 SN ${sn}？`)) return
  try {
    await api.deleteProductSn(selectedCode.value, sn)
    await selectProduct(selectedCode.value)
    notice.value = 'SN 已删除'
  } catch (e: any) {
    error.value = friendlyError(e, 'SN 删除失败')
  }
}
function copySn(sn: string) { void navigator.clipboard?.writeText(sn) }
function exportSn() {
  const csv = ['SN', ...allRows.value.map((r: any) => r.sn)].join('\n')
  const url = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${selectedCode.value || 'product'}-SN清单.csv`
  link.click()
  URL.revokeObjectURL(url)
}
function downloadTemplate() { downloadSnTemplate() }

onMounted(loadProfiles)
</script>

<style scoped>
.product-page { max-width: 1180px; margin: 0 auto; }
.head, .panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
h2 { font-size: 20px; }
h3 { font-size: 15px; }
.row, .import-actions, .pager, .toolbar.inline { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.sub, .mini, .empty { color: var(--muted); }
.delete-sn-card { margin-top: 12px; border-color: var(--red-soft); }
.delete-sn-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 10px; }
.selected-count { margin-right: auto; color: var(--muted); font-size: 12px; }
.selected-count b { color: var(--red); font-size: 14px; }
.sub { font-size: 12px; margin-top: 4px; }
.mini { font-size: 11px; }
.card { border: 1px solid var(--line); border-radius: 8px; background: var(--white); padding: 12px; }
.product-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 10px; align-items: start; margin-top: 10px; }
.product-list { display: grid; gap: 6px; }
.product-item { display: grid; gap: 2px; text-align: left; border: 1px solid transparent; border-radius: 7px; padding: 8px; background: transparent; cursor: pointer; font-family: inherit; }
.product-item:hover, .product-item.active { border-color: var(--tech-blue); background: var(--tech-blue-soft); }
.product-item b { font-size: 12px; }
.product-item small { color: var(--muted); }
.product-main { display: grid; gap: 10px; min-width: 0; }
.name-row { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 8px; margin: 8px 0 6px; }
.import-grid { display: grid; gap: 8px; margin-top: 8px; }
.import-grid label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.full-line { grid-column: 1 / -1; }
.single-add-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.drop-label { display: block; color: var(--muted); font-size: 11px; margin-bottom: 4px; }
.sn-drop-zone { border: 1px dashed var(--line); border-radius: 8px; padding: 14px; text-align: center; color: var(--muted); font-size: 12px; cursor: pointer; background: var(--bg); }
.sn-drop-zone:hover, .sn-drop-zone.active { border-color: var(--tech-blue); color: var(--tech-blue); background: var(--tech-blue-soft); }
.native-file-input { display: none !important; }
.import-actions { margin-top: 10px; }
.skip-list { margin-top: 8px; max-height: 120px; overflow: auto; border: 1px solid var(--line); border-radius: 6px; }
.skip-row { display: grid; grid-template-columns: 160px 1fr; gap: 8px; padding: 5px 8px; border-bottom: 1px solid var(--line); font-size: 11px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid var(--line); padding: 7px; text-align: left; }
th { color: var(--muted); }
.ops { white-space: nowrap; }
.link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; font-family: inherit; font-size: 11px; }
.danger-link { color: var(--red); }
.msg { padding: 9px 12px; border-radius: 5px; margin-bottom: 10px; }
.msg.err { background: var(--red-soft); color: var(--red); }
.msg.ok { background: var(--green-soft); color: var(--green); }
.modal-mask { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(4,8,18,.65); }
.modal { width: 100%; max-width: 480px; background: var(--white); border-radius: 10px; padding: 18px; }
.modal label { display: grid; gap: 5px; color: var(--muted); font-size: 12px; margin-top: 12px; }
input, textarea { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 8px; font-family: inherit; color: var(--ink); background: var(--white); }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
@media (max-width: 760px) { .head { flex-direction: column; } .product-layout { grid-template-columns: 1fr; } .product-list { max-height: 220px; overflow: auto; } .single-add-row { grid-template-columns: 1fr; } }
</style>
