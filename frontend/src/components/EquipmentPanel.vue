<template>
  <section class="card equipment-panel">
    <div class="panel-head">
      <div>
        <h3>设备台账</h3>
        <p class="sub">像站点一样管理设备：左侧选择、中间查看、右侧维护。</p>
      </div>
      <div class="row">
        <button class="btn sm" type="button" :disabled="loading" @click="reload">重新加载</button>
        <button v-if="canManage" class="btn sm" type="button" @click="downloadTemplate">下载模板</button>
        <button v-if="canManage" class="btn sm primary" type="button" @click="importOpen = true">导入设备</button>
      </div>
    </div>

    <div v-if="error" class="msg err">{{ error }}</div>
    <div v-if="notice" class="msg ok">{{ notice }}</div>
    <div v-if="!canManage" class="msg">当前账号无 `machine:manage` 权限，仅可查看设备台账。</div>

    <div class="toolbar">
      <label>搜索<input v-model="filters.q" placeholder="编号 / 名称 / 工站 / 产品" @keyup.enter="reload" /></label>
      <label>状态
        <select v-model="filters.status" @change="reload">
          <option value="">全部状态</option>
          <option v-for="s in statusOptions" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </label>
      <label>分类<input v-model="filters.category" placeholder="如：生产设备" @keyup.enter="reload" /></label>
      <div class="row">
        <button class="btn sm" type="button" :disabled="loading" @click="reload">查询</button>
        <button class="btn sm" type="button" @click="resetFilters">重置</button>
      </div>
    </div>

    <div class="device-layout">
      <aside class="device-list-panel">
        <div class="panel-title">设备列表</div>
        <button v-if="canManage" class="btn sm primary full-btn" type="button" @click="openForm()">新增设备</button>
        <div v-for="group in stationGroups" :key="group.key" class="device-list-group">
          <div class="group-head"><b>{{ group.label }}</b><span>{{ group.items.length }}</span></div>
          <button
            v-for="row in group.items"
            :key="row.code"
            class="device-list-item"
            :class="{ active: selectedCode === row.code }"
            type="button"
            :title="canManage ? '双击编辑设备' : ''"
            @click="selectDevice(row)"
            @dblclick.stop="canManage && openForm(row)"
          >
            <span class="mono">{{ row.code }}</span>
            <b>{{ row.name }}</b>
            <small>{{ row.productCode || '未关联产品' }}</small>
          </button>
        </div>
        <div v-if="!devices.length" class="empty">{{ hasFilter ? '没有符合筛选条件的设备' : '暂无设备，点击“新增设备”开始建档' }}</div>
      </aside>

      <main class="device-card-panel">
        <div class="panel-title">设备卡片布局</div>
        <div v-for="group in stationGroups" :key="group.key" class="device-card-group">
          <div class="section-title">{{ group.label }}</div>
          <div class="device-cards">
            <button
              v-for="(row, index) in group.items"
              :key="row.code"
              class="device-card"
              :class="{ active: selectedCode === row.code }"
              type="button"
              :title="canManage ? '双击编辑设备' : ''"
              @click="selectDevice(row)"
              @dblclick.stop="canManage && openForm(row)"
            >
              <div class="device-card-top"><span class="device-index">{{ index + 1 }}</span><span class="mono">{{ row.code }}</span></div>
              <b>{{ row.name }}</b>
              <div class="device-card-tags">
                <span class="tag" :class="'st-' + row.status">{{ statusLabel(row.status) }}</span>
                <span class="chip">{{ row.productCode || '未关联产品' }}</span>
              </div>
              <small>{{ (row.maintenance || []).length }} 条维护记录</small>
            </button>
          </div>
        </div>
        <div v-if="!devices.length" class="empty">{{ hasFilter ? '没有符合筛选条件的设备' : '暂无设备卡片' }}</div>
      </main>

      <aside class="device-property-panel">
        <div class="panel-title">设备属性</div>
        <template v-if="selectedDevice">
          <label>设备编号<input :value="selectedDevice.code" disabled /></label>
          <label>设备名称<input v-model="nameDraft" :disabled="!canManage" /></label>
          <button v-if="canManage" class="btn sm primary full-btn" type="button" @click="saveName">保存名称</button>
          <label>关联工站<input :value="relationLabel(selectedDevice.relatedStations, selectedDevice.stationName || selectedDevice.stationCode)" disabled /></label>
          <label>关联产品<input :value="relationLabel(selectedDevice.relatedProducts, productLabel(selectedDevice, false))" disabled /></label>
          <label>关联人员<input :value="relationLabel(selectedDevice.relatedPersons, selectedDevice.operator)" disabled /></label>
          <label>运行状态<input :value="statusLabel(selectedDevice.status)" disabled /></label>
          <label>维护记录<input :value="(selectedDevice.maintenance || []).length + ' 条'" disabled /></label>
          <div class="property-actions">
            <button class="btn sm" type="button" @click="openMaintenance(selectedDevice)">维护记录</button>
            <button v-if="canManage" class="btn sm danger" type="button" @click="remove(selectedDevice)">删除设备</button>
          </div>
        </template>
        <div v-else class="empty">请选择设备</div>
      </aside>
    </div>

    <div v-if="formOpen" class="modal-mask" @click.self="formOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <div class="panel-head"><b>{{ form.mode === 'create' ? '新增设备' : '编辑设备' }}</b><button class="btn sm" type="button" @click="formOpen = false">关闭</button></div>
        <div v-if="formError" class="msg err">{{ formError }}</div>
        <p class="sub">系统自动生成设备编号，并根据名称自动关联工站与产品；其他信息无需填写。</p>
        <div class="form-grid single">
          <label>设备名称<input v-model="form.name" autofocus /></label>
        </div>
        <template v-if="form.mode === 'edit'">
          <div class="form-grid">
            <label>关联产品
              <select v-model="form.productCode">
                <option value="">不关联产品</option>
                <option v-for="item in options.products" :key="item.code" :value="item.code">{{ item.code }} · {{ item.name }}</option>
              </select>
            </label>
            <label>关联工艺 / 工站
              <select v-model="form.stationCode">
                <option value="">不关联工站</option>
                <option v-for="item in options.stations" :key="item.code" :value="item.code">{{ item.code }} · {{ item.name }}</option>
              </select>
            </label>
            <label>关联人员
              <select v-model="form.operator">
                <option value="">不关联人员</option>
                <option v-for="item in options.persons" :key="item.code || item.username" :value="item.code || item.username">{{ item.name }}（{{ item.code || item.username }}）</option>
              </select>
            </label>
          </div>
        </template>
        <div class="modal-foot">
          <button class="btn" type="button" @click="formOpen = false">取消</button>
          <button class="btn primary" type="button" @click="saveDevice">保存设备</button>
        </div>
      </div>
    </div>

    <div v-if="importOpen" class="modal-mask" @click.self="importOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <div class="panel-head"><b>导入设备</b><button class="btn sm" type="button" @click="importOpen = false">关闭</button></div>
        <div v-if="importError" class="msg err">{{ importError }}</div>
        <div v-if="importResult" class="msg ok">
          成功 {{ importResult.createdCount }} 台，跳过 {{ importResult.skippedCount }} 台。
        </div>
        <div v-if="importResult?.skipped?.length" class="table-scroll small-table">
          <table><thead><tr><th>行</th><th>编码</th><th>原因</th></tr></thead><tbody>
            <tr v-for="(item, i) in importResult.skipped" :key="i"><td>{{ item.row }}</td><td class="mono">{{ item.code || '—' }}</td><td>{{ item.reason }}</td></tr>
          </tbody></table>
        </div>
        <p class="sub">支持 `.xlsx / .xls / .csv`，可点击选择或直接拖入。默认按“单列设备名称（无表头）”读取；也兼容带设备名称表头的旧模板。编号自动分配，工站与产品按名称自动关联。</p>
        <label
          class="file-label import-drop"
          :class="{ active: importDragging }"
          @dragover.prevent="importDragging = true"
          @dragenter.prevent="importDragging = true"
          @dragleave.prevent="importDragging = false"
          @drop.prevent="onImportDrop"
        >
          {{ selectedImportFile ? selectedImportFile.name : '点击选择文件，或拖拽 Excel / CSV 到这里' }}
          <input ref="importInput" type="file" accept=".xlsx,.xls,.csv" @change="onImportFileChange" />
        </label>
        <div class="modal-foot">
          <button class="btn" type="button" @click="importOpen = false">取消</button>
          <button class="btn primary" type="button" :disabled="importing" @click="importFile">{{ importing ? '导入中…' : '开始导入' }}</button>
        </div>
      </div>
    </div>

    <div v-if="maintenanceOpen" class="modal-mask" @click.self="maintenanceOpen = false">
      <div class="modal wide" role="dialog" aria-modal="true">
        <div class="panel-head">
          <div><b>点检维护记录</b><p class="sub mono">{{ maintenanceDevice?.code }} · {{ maintenanceDevice?.name }}</p></div>
          <button class="btn sm" type="button" @click="maintenanceOpen = false">关闭</button>
        </div>
        <div v-if="maintenanceError" class="msg err">{{ maintenanceError }}</div>
        <div v-if="canManage" class="maintenance-form">
          <label>日期<input v-model="maintenanceForm.date" type="date" /></label>
          <label>类型<select v-model="maintenanceForm.type"><option v-for="t in maintenanceTypes" :key="t" :value="t">{{ t }}</option></select></label>
          <label>执行人<input v-model="maintenanceForm.operator" /></label>
          <label>结果<select v-model="maintenanceForm.result"><option v-for="r in maintenanceResults" :key="r" :value="r">{{ r }}</option></select></label>
          <label>下次日期<input v-model="maintenanceForm.nextDate" type="date" /></label>
          <label class="full">内容<input v-model="maintenanceForm.content" placeholder="点检/保养/维修内容" /></label>
          <button class="btn primary" type="button" @click="saveMaintenance">{{ maintenanceForm.id ? '保存记录' : '添加记录' }}</button>
          <button v-if="maintenanceForm.id" class="btn" type="button" @click="resetMaintenanceForm">取消编辑</button>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>日期</th><th>类型</th><th>内容</th><th>执行人</th><th>结果</th><th>下次</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="item in maintenanceRows" :key="item.id">
                <td>{{ item.date }}</td><td>{{ item.type }}</td><td>{{ item.content }}</td>
                <td>{{ item.operator || '—' }}</td><td>{{ item.result }}</td><td>{{ item.nextDate || '—' }}</td>
                <td>
                  <button v-if="canManage" class="link" type="button" @click="editMaintenance(item)">编辑</button>
                  <button v-if="canManage" class="link danger-link" type="button" @click="removeMaintenance(item)">删除</button>
                </td>
              </tr>
              <tr v-if="!maintenanceRows.length"><td colspan="7" class="empty">暂无点检维护记录</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import * as XLSX from 'xlsx'
import { api, getUser } from '../api'
import { sharedPerms } from '../stores/permStore'

const devices = ref<any[]>([])
const summary = ref<any>({ total: 0, counts: [] })
const options = ref<any>({ products: [], stations: [], persons: [] })
const selectedCode = ref('')
const nameDraft = ref('')
const loading = ref(false)
const error = ref('')
const notice = ref('')
const formError = ref('')
const importError = ref('')
const maintenanceError = ref('')
const formOpen = ref(false)
const importOpen = ref(false)
const importing = ref(false)
const importDragging = ref(false)
const selectedImportFile = ref<File | null>(null)
const importResult = ref<any>(null)
const maintenanceOpen = ref(false)
const maintenanceDevice = ref<any>(null)
const importInput = ref<HTMLInputElement | null>(null)
const filters = reactive<any>({ q: '', status: '', category: '' })
const hasFilter = computed(() => !!(filters.q || filters.status || filters.category))
const statusOptions = [
  { value: 'running', label: '运行' }, { value: 'idle', label: '空闲' },
  { value: 'stopped', label: '停机' }, { value: 'maintenance', label: '维修' },
  { value: 'scrapped', label: '报废' },
]
const maintenanceTypes = ['点检', '保养', '维修', '校准']
const maintenanceResults = ['正常', '异常', '待处理', '已完成']

type EquipmentImportTemplate = {
  key: string
  label: string
  headerRows: number
  match: (headers: string[], matrix: any[][]) => boolean
  fieldIndex: (headers: string[]) => Record<string, number>
}
const EQUIPMENT_IMPORT_ALIASES: Record<string, string[]> = {
  code: ['设备编号', '设备编码', 'code'],
  name: ['设备名称', '名称', 'name'],
  model: ['设备型号', '型号', 'model'],
  brand: ['品牌', 'brand'],
  serialNo: ['出厂序列号', '序列号', 'serialNo'],
  category: ['设备类别', '类别', 'category'],
  location: ['安装位置', '位置', 'location'],
  department: ['所属部门', '部门', 'department'],
  stationCode: ['关联站点', '关联站点编码', 'stationCode'],
  status: ['运行状态', '状态', 'status'],
  operator: ['责任人', 'operator'],
  phone: ['联系电话', '电话', 'phone'],
  purchaseDate: ['购置日期', 'purchaseDate'],
  warrantyDate: ['保修到期', 'warrantyDate'],
  remark: ['备注', 'remark'],
}
const EQUIPMENT_IMPORT_TEMPLATES: EquipmentImportTemplate[] = [
  {
    key: 'header',
    label: '带表头设备资料',
    headerRows: 1,
    match: (headers) => headers.some((header) => EQUIPMENT_IMPORT_ALIASES.name.includes(header)),
    fieldIndex: (headers) => indexFromHeaders(headers),
  },
  {
    key: 'name-list',
    label: '单列设备名称（无表头）',
    headerRows: 0,
    match: () => true,
    fieldIndex: () => ({ name: 0 }),
  },
]

const form = reactive<any>({
  mode: 'create', id: '', code: '', name: '', model: '', brand: '', serialNo: '',
  category: '', location: '', department: '', stationCode: '', status: 'idle',
  operator: '', phone: '', purchaseDate: '', warrantyDate: '', remark: '',
})
const maintenanceForm = reactive<any>({ id: '', date: '', type: '点检', content: '', operator: '', result: '正常', nextDate: '' })
const canManage = computed(() => getUser()?.role === 'admin' || sharedPerms.value.includes('machine:manage'))
const maintenanceRows = computed(() => maintenanceDevice.value?.maintenance || [])
const selectedDevice = computed(() => devices.value.find(d => d.code === selectedCode.value) || null)
const stationGroups = computed(() => {
  const map = new Map<string, { key: string; label: string; items: any[] }>()
  devices.value.forEach(device => {
    const key = String(device.stationCode || 'none')
    const label = device.stationName || device.stationCode || '未关联工站'
    if (!map.has(key)) map.set(key, { key, label, items: [] })
    map.get(key)!.items.push(device)
  })
  return Array.from(map.values()).sort((a, b) => a.key === 'none' ? 1 : b.key === 'none' ? -1 : a.label.localeCompare(b.label))
})

function statusLabel(value: string) { return statusOptions.find(s => s.value === value)?.label || value || '—' }
function productLabel(row: any, withFallback = true) {
  return row.productName ? `${row.productCode || ''} ${row.productName}`.trim() : (row.productCode || (withFallback ? '未关联' : ''))
}
function relationLabel(items: any[], fallback = '') {
  if (Array.isArray(items) && items.length) return items.map(item => `${item.name || item.code}（${item.code}）`).join('、')
  return fallback || '未关联'
}
function selectDevice(row: any) {
  selectedCode.value = row.code
  nameDraft.value = row.name || ''
}
function today() { return new Date().toISOString().slice(0, 10) }

async function loadOptions() {
  try { options.value = await api.equipmentOptions() }
  catch { options.value = { products: [], stations: [], persons: [] } }
}
async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [list, stats] = await Promise.all([
      api.equipmentList({ q: filters.q, status: filters.status, category: filters.category }),
      api.equipmentSummary(),
    ])
    devices.value = list
    summary.value = stats
    if (!selectedCode.value || !list.some(d => d.code === selectedCode.value)) {
      if (list.length) selectDevice(list[0])
      else { selectedCode.value = ''; nameDraft.value = '' }
    } else {
      nameDraft.value = selectedDevice.value?.name || ''
    }
  } catch (e: any) {
    error.value = e.message || '设备台账加载失败'
  } finally {
    loading.value = false
  }
}
function loadDevices() { void reload() }
function resetFilters() { filters.q = ''; filters.status = ''; filters.category = ''; void reload() }

function openForm(row?: any) {
  formError.value = ''
  form.mode = row?.code ? 'edit' : 'create'
  form.code = row?.code || ''
  form.name = row?.name || ''
  form.productCode = row?.productCode || ''
  form.stationCode = row?.stationCode || ''
  form.operator = row?.relatedPersons?.[0]?.code || row?.operator || ''
  void loadOptions()
  formOpen.value = true
}
function buildPayload() {
  const name = String(form.name || '').trim()
  if (form.mode === 'create') return { name }
  const product = (options.value.products || []).find((item: any) => item.code === form.productCode)
  const station = (options.value.stations || []).find((item: any) => item.code === form.stationCode)
  return {
    name,
    productCode: form.productCode || '',
    productName: product?.name || '',
    stationCode: form.stationCode || '',
    stationName: station?.name || '',
    operator: form.operator || '',
  }
}
async function saveDevice() {
  formError.value = ''
  try {
    const saved = form.mode === 'edit'
      ? await api.updateEquipment(form.code, buildPayload())
      : await api.createEquipment(buildPayload())
    selectedCode.value = saved.code
    nameDraft.value = saved.name || ''
    formOpen.value = false
    notice.value = form.mode === 'edit' ? `设备已保存：${saved.code}` : `设备已新增：${saved.code}`
    await reload()
  } catch (e: any) {
    formError.value = e.message || '设备保存失败'
  }
}
async function saveName() {
  if (!selectedDevice.value) return
  const name = String(nameDraft.value || '').trim()
  if (!name) { error.value = '设备名称不能为空'; return }
  try {
    await api.updateEquipment(selectedDevice.value.code, { name })
    notice.value = '设备名称已保存'
    await reload()
  } catch (e: any) {
    error.value = e.message || '设备名称保存失败'
  }
}
async function remove(row: any) {
  if (!window.confirm(`确认删除设备 ${row.code}？`)) return
  try {
    await api.deleteEquipment(row.code)
    notice.value = '设备已删除'
    await reload()
  } catch (e: any) {
    error.value = e.message || '设备删除失败'
  }
}

function normalizeImportHeader(value: any) {
  return String(value ?? '').trim().toLowerCase().replace(/[\s_\-（）()]/g, '')
}
function indexFromHeaders(headers: string[]) {
  const index: Record<string, number> = {}
  Object.entries(EQUIPMENT_IMPORT_ALIASES).forEach(([field, aliases]) => {
    index[field] = headers.findIndex(header => aliases.map(normalizeImportHeader).includes(header))
  })
  return index
}
function firstText(row: any[], index: number) {
  const values = index >= 0 ? [row[index], ...row] : row
  for (const value of values) {
    const text = String(value ?? '').trim()
    if (text) return text
  }
  return ''
}
function resolveImportTemplate(matrix: any[][]) {
  const headers = (matrix[0] || []).map(normalizeImportHeader)
  return EQUIPMENT_IMPORT_TEMPLATES.find(template => template.match(headers, matrix)) || EQUIPMENT_IMPORT_TEMPLATES[EQUIPMENT_IMPORT_TEMPLATES.length - 1]
}
function normalizeDate(value: any) {
  if (value === undefined || value === null || value === '') return ''
  if (value instanceof Date) return value.toISOString().slice(0, 10)
  if (typeof value === 'number') {
    const parsed = XLSX.SSF.parse_date_code(value)
    if (parsed) return `${parsed.y}-${String(parsed.m).padStart(2, '0')}-${String(parsed.d).padStart(2, '0')}`
  }
  const text = String(value).trim()
  const match = /^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/.exec(text)
  return match ? `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}` : text
}
function normalizeStatus(value: any) {
  const raw = String(value || '').trim().toLowerCase()
  const map: Record<string, string> = {
    '运行': 'running', '运行中': 'running', '在用': 'running', 'running': 'running',
    '空闲': 'idle', '待机': 'idle', 'idle': 'idle',
    '停机': 'stopped', '停用': 'stopped', 'stopped': 'stopped',
    '维修': 'maintenance', '维修中': 'maintenance', '保养': 'maintenance', '维护': 'maintenance', 'maintenance': 'maintenance',
    '报废': 'scrapped', 'scrapped': 'scrapped',
  }
  return map[raw] || (raw || 'idle')
}
function onImportFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedImportFile.value = input.files?.[0] || null
}
function onImportDrop(event: DragEvent) {
  importDragging.value = false
  selectedImportFile.value = event.dataTransfer?.files?.[0] || null
  if (importInput.value && selectedImportFile.value) importInput.value.files = event.dataTransfer?.files || null
}
async function importFile() {
  const file = selectedImportFile.value || importInput.value?.files?.[0]
  if (!file) { importError.value = '请选择 Excel 或 CSV 文件'; return }
  importError.value = ''
  importResult.value = null
  importing.value = true
  try {
    const buffer = await file.arrayBuffer()
    const isCsv = file.name.toLowerCase().endsWith('.csv')
    const book = isCsv
      ? XLSX.read(new TextDecoder('utf-8').decode(buffer).replace(/^\uFEFF/, ''), { type: 'string', cellDates: true, raw: false })
      : XLSX.read(buffer, { type: 'array', cellDates: true, raw: false })
    const sheet = book.Sheets[book.SheetNames[0]]
    const matrix = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' }) as any[][]
    const template = resolveImportTemplate(matrix)
    const headers = (matrix[0] || []).map(normalizeImportHeader)
    const idx = template.fieldIndex(headers)
    const rows = matrix.slice(template.headerRows).filter(r => r.some(v => String(v ?? '').trim())).map(r => ({
      code: idx.code >= 0 ? String(r[idx.code] ?? '').trim().toUpperCase() : '',
      name: firstText(r, idx.name ?? 0),
      model: idx.model >= 0 ? String(r[idx.model] ?? '').trim() : '',
      brand: idx.brand >= 0 ? String(r[idx.brand] ?? '').trim() : '',
      serialNo: idx.serialNo >= 0 ? String(r[idx.serialNo] ?? '').trim().toUpperCase() : '',
      category: idx.category >= 0 ? String(r[idx.category] ?? '').trim() : '',
      location: idx.location >= 0 ? String(r[idx.location] ?? '').trim() : '',
      department: idx.department >= 0 ? String(r[idx.department] ?? '').trim() : '',
      stationCode: idx.stationCode >= 0 ? String(r[idx.stationCode] ?? '').trim().toUpperCase() : '',
      status: idx.status >= 0 ? normalizeStatus(r[idx.status]) : 'idle',
      operator: idx.operator >= 0 ? String(r[idx.operator] ?? '').trim() : '',
      phone: idx.phone >= 0 ? String(r[idx.phone] ?? '').trim() : '',
      purchaseDate: idx.purchaseDate >= 0 ? normalizeDate(r[idx.purchaseDate]) : '',
      warrantyDate: idx.warrantyDate >= 0 ? normalizeDate(r[idx.warrantyDate]) : '',
      remark: idx.remark >= 0 ? String(r[idx.remark] ?? '').trim() : '',
    })).filter(row => row.name)
    importResult.value = await api.importEquipment(rows)
    notice.value = `成功导入 ${importResult.value.createdCount} 台设备，跳过 ${importResult.value.skippedCount} 台`
    selectedImportFile.value = null
    if (importInput.value) importInput.value.value = ''
    await reload()
  } catch (e: any) {
    importError.value = e.message || '设备导入失败'
  } finally {
    importing.value = false
  }
}
function downloadTemplate() {
  const rows = [['V2.5夹爪工装'], ['V2.9夹爪工装']]
  const csv = '\uFEFF' + rows.map(row => row.join(',')).join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = '设备导入模板.csv'; link.click(); URL.revokeObjectURL(url)
}
function exportCsv() {
  const headers = ['设备编号', '设备名称', '关联工站', '关联产品', '状态', '维护记录数']
  const rows = devices.value.map(d => [d.code, d.name, d.stationName || d.stationCode || '', d.productName ? `${d.productCode || ''} ${d.productName}` : (d.productCode || ''), statusLabel(d.status), (d.maintenance || []).length])
  const csv = '\uFEFF' + [headers, ...rows].map(row => row.map(v => `"${String(v || '').replace(/"/g, '""')}"`).join(',')).join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = '设备台账.csv'; link.click(); URL.revokeObjectURL(url)
}

function resetMaintenanceForm() {
  Object.assign(maintenanceForm, { id: '', date: today(), type: '点检', content: '', operator: '', result: '正常', nextDate: '' })
}
async function openMaintenance(row: any) {
  maintenanceDevice.value = await api.equipmentDetail(row.code)
  maintenanceError.value = ''
  resetMaintenanceForm()
  maintenanceOpen.value = true
}
function editMaintenance(item: any) {
  Object.assign(maintenanceForm, {
    id: item.id, date: item.date || '', type: item.type, content: item.content,
    operator: item.operator || '', result: item.result, nextDate: item.nextDate || '',
  })
}
async function saveMaintenance() {
  if (!maintenanceDevice.value) return
  maintenanceError.value = ''
  try {
    const payload = { ...maintenanceForm }
    delete payload.id
    if (maintenanceForm.id) await api.updateEquipmentMaintenance(maintenanceDevice.value.code, maintenanceForm.id, payload)
    else await api.addEquipmentMaintenance(maintenanceDevice.value.code, payload)
    maintenanceDevice.value = await api.equipmentDetail(maintenanceDevice.value.code)
    resetMaintenanceForm()
    notice.value = '维护记录已保存'
    await reload()
  } catch (e: any) {
    maintenanceError.value = e.message || '维护记录保存失败'
  }
}
async function removeMaintenance(item: any) {
  if (!maintenanceDevice.value || !window.confirm(`确认删除 ${item.date} ${item.type} 记录？`)) return
  try {
    await api.deleteEquipmentMaintenance(maintenanceDevice.value.code, item.id)
    maintenanceDevice.value = await api.equipmentDetail(maintenanceDevice.value.code)
    notice.value = '维护记录已删除'
    await reload()
  } catch (e: any) {
    maintenanceError.value = e.message || '维护记录删除失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.equipment-panel { margin-bottom: 12px; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
h3 { font-size: 16px; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
.sub, .mini, .empty { color: var(--muted); }
.sub { font-size: 12px; margin-top: 4px; }
.device-layout { display: grid; grid-template-columns: 230px minmax(360px, 1fr) 250px; gap: 10px; margin-top: 12px; align-items: start; }
.device-list-panel, .device-card-panel, .device-property-panel { border: 1px solid var(--line); border-radius: 9px; padding: 11px; background: var(--white); }
.panel-title { font-size: 13px; font-weight: 700; margin-bottom: 10px; }
.full-btn { width: 100%; margin-bottom: 10px; }
.device-list-group { border-top: 1px solid var(--line); padding-top: 8px; margin-top: 8px; }
.group-head, .section-title { display: flex; justify-content: space-between; color: var(--muted); font-size: 12px; margin-bottom: 6px; }
.device-list-item { display: grid; grid-template-columns: 58px 1fr; gap: 2px 7px; width: 100%; text-align: left; border: 1px solid transparent; border-radius: 7px; padding: 7px; background: transparent; cursor: pointer; font-family: inherit; }
.device-list-item:hover, .device-list-item.active { border-color: var(--tech-blue); background: var(--tech-blue-soft); }
.equipment-panel .device-list-item, .equipment-panel .device-card { user-select: none; }
.device-list-item span { grid-row: 1 / 3; color: var(--tech-blue); font-size: 11px; align-self: center; }
.device-list-item b { font-size: 12px; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.device-list-item small { color: var(--muted); font-size: 10px; }
.device-card-group + .device-card-group { margin-top: 12px; }
.device-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.device-card { border: 1px solid var(--line); border-radius: 9px; padding: 9px; background: var(--bg); text-align: left; cursor: pointer; font-family: inherit; min-height: 105px; }
.device-card:hover, .device-card.active { border-color: var(--tech-blue); background: var(--tech-blue-soft); }
.device-card-top { display: flex; align-items: center; gap: 7px; margin-bottom: 6px; color: var(--tech-blue); font-size: 11px; }
.device-index { width: 20px; height: 20px; display: grid; place-items: center; border-radius: 50%; background: var(--white); border: 1px solid var(--line); }
.device-card > b { display: block; font-size: 13px; margin-bottom: 7px; color: var(--ink); }
.device-card > small { display: block; color: var(--muted); font-size: 10px; margin-top: 7px; }
.device-card-tags { display: flex; gap: 5px; flex-wrap: wrap; }
.chip { border-radius: 10px; padding: 2px 7px; font-size: 10px; background: var(--white); color: var(--muted); border: 1px solid var(--line); }
.device-property-panel label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; margin-bottom: 8px; }
.property-actions { display: flex; gap: 7px; margin-top: 10px; flex-wrap: wrap; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; margin: 12px 0; }
.stats article { border: 1px solid var(--line); border-radius: 8px; padding: 9px; }
.stats span { display: block; color: var(--muted); font-size: 11px; }
.stats b { font-size: 18px; }
.toolbar { display: flex; gap: 10px; align-items: end; flex-wrap: wrap; margin-bottom: 10px; }
.toolbar label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; min-width: 180px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; }
th { color: var(--muted); font-weight: 600; }
.tag { border-radius: 10px; padding: 2px 7px; font-size: 11px; background: var(--tech-blue-soft); color: var(--tech-blue); }
.st-idle { background: #fff4d6; color: #8a6100; }
.st-stopped { background: var(--red-soft); color: var(--red); }
.st-maintenance { background: #efe5ff; color: #6b41a8; }
.st-scrapped { background: #eee; color: #666; }
.link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; padding: 0 6px 0 0; font-family: inherit; font-size: 11px; }
.danger-link { color: var(--red); }
.empty { text-align: center; }
.msg { padding: 9px 12px; border-radius: 5px; margin-bottom: 10px; }
.msg.err { background: var(--red-soft); color: var(--red); }
.msg.ok { background: var(--green-soft); color: var(--green); }
.modal-mask { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(4,8,18,.65); }
.modal { width: 100%; max-width: 780px; max-height: 92dvh; overflow: auto; background: var(--white); border-radius: 10px; padding: 18px; }
.modal.wide { max-width: 1000px; }
.form-grid, .maintenance-form { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; margin-top: 12px; }
.maintenance-form { grid-template-columns: repeat(5, minmax(0,1fr)); align-items: end; }
.form-grid label, .maintenance-form label, .file-label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.full { grid-column: 1 / -1; }
input, select, textarea { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 7px 8px; font-family: inherit; color: var(--ink); background: var(--white); }
.file-label { margin-top: 12px; max-width: 420px; }
.import-drop { display: block; width: 100%; max-width: none; border: 1px dashed var(--line); border-radius: 8px; padding: 18px; text-align: center; color: var(--muted); cursor: pointer; background: var(--bg); }
.import-drop:hover, .import-drop.active { border-color: var(--tech-blue); color: var(--tech-blue); background: var(--tech-blue-soft); }
.import-drop input { display: none !important; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.small-table { margin-top: 10px; max-height: 160px; overflow: auto; }
@media (max-width: 1100px) { .device-layout { grid-template-columns: 210px 1fr; } .device-property-panel { grid-column: 1 / -1; } }
@media (max-width: 900px) { .panel-head { flex-direction: column; } .maintenance-form { grid-template-columns: 1fr 1fr; } }
@media (max-width: 700px) { .device-layout { grid-template-columns: 1fr; } .device-property-panel { grid-column: auto; } .device-cards { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .form-grid, .maintenance-form { grid-template-columns: 1fr; } .full { grid-column: auto; } }
</style>
