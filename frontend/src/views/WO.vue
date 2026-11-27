<template>
  <div>
    <div class="grid g2">
      <div class="card">
        <h2>新建工单</h2>
        <p class="sub">建单时只确定站点序列；计划数按实际导入 SN 自动计算，装箱按包装工站实际数量完成。</p>
        <div class="field">
          <label>工单号（自动生成）</label>
          <input v-model="form.wo_no" class="mono" readonly placeholder="填写产品和流程后自动生成" />
          <p class="mini">{{ woNoLoading ? '正在生成工单号…' : '按日期和当天流水自动编号，提交时以后端结果为准。' }}</p>
        </div>
        <div class="field"><label>产品</label>
          <div class="row">
            <select v-model="form.product" style="flex:1"><option v-for="p in products" :key="p.code" :value="p.name">{{ p.name }}</option></select>
            <router-link v-if="hasProductProfile" class="btn" :to="{ path: '/product-info', query: { product: form.product } }">资料</router-link>
          </div>
        </div>
        <div class="field"><label>批次</label><input v-model="form.batch" placeholder="第一批" /></div>
        <div class="field">
          <label>流程（按过站顺序）</label>
          <select v-model="selectedFlowKey" :disabled="!flowOptions.length" @change="applyFlow">
            <option value="">{{ flowOptions.length ? '请选择已配置流程' : '暂无已配置流程' }}</option>
            <optgroup v-if="configFlowOptions.length" label="工艺流程">
              <option v-for="flow in configFlowOptions" :key="flow.key" :value="flow.key">{{ flow.label }}</option>
            </optgroup>
            <optgroup v-if="historyFlowOptions.length" label="历史工单流程">
              <option v-for="flow in historyFlowOptions" :key="flow.key" :value="flow.key">{{ flow.label }}</option>
            </optgroup>
          </select>
          <div v-if="selectedStations.length" class="flow-preview">
            <span v-for="(station, index) in selectedStations" :key="station + index"><b>{{ index + 1 }}</b>{{ station }}</span>
          </div>
          <p v-else class="mini">请先在工艺管理中配好站点流程，或选择历史工单已用流程。</p>
        </div>
        <div class="field"><label>产出地点</label><select v-model="form.location"><option>戴盟公司</option><option>联想智造</option></select></div>
        <div class="grid2">
          <div class="field"><label>关联设备</label><select v-model="form.relatedEquipment" multiple><option v-for="item in relationOptions.equipment" :key="'e-' + item.code" :value="item.code">{{ item.code }} · {{ item.name }}</option></select></div>
          <div class="field"><label>关联人员</label><select v-model="form.relatedPersons" multiple><option v-for="item in relationOptions.persons" :key="'u-' + item.code" :value="item.code">{{ item.code }} · {{ item.name }}</option></select></div>
        </div>
        <p class="mini">工单的产品、流程和上面的关联对象会自动同步到工艺、设备、人员对应记录。</p>
        <button class="btn primary" @click="create">建单</button>
      </div>

      <div class="card">
        <h2>导入 SN 清单</h2>
        <p class="sub">支持单条录入、批量粘贴或上传表格；重复 SN 自动跳过（幂等）</p>
        <div class="field"><label>选择工单</label><select v-model="importWO"><option value="">请选择</option><option v-for="w in wos" :key="w.id" :value="w.id">{{ w.wo_no }} · {{ w.product }}</option></select></div>
        <div class="import-tabs">
          <button :class="{ active: importMode === 'single' }" @click="importMode = 'single'">单条导入</button>
          <button :class="{ active: importMode === 'batch' }" @click="importMode = 'batch'">批量导入</button>
        </div>
        <div v-if="importMode === 'single'">
          <div class="field"><label>SN</label><input v-model="singleSn" class="mono" placeholder="16 位 SN" @keyup.enter="importSingle" /></div>
          <button class="btn primary" :disabled="!importWO || !singleSn.trim()" @click="importSingle">导入单条</button>
        </div>
        <div v-else>
          <div class="field"><label>SN 清单（每行一个，或逗号分隔）</label><textarea v-model="snText" rows="7" class="mono" placeholder="DAP93226AS00019D&#10;DAP93226AS000294"></textarea></div>
          <div class="toolbar">
            <button class="btn" @click="downloadSnTemplate">下载导入模板</button>
            <label class="btn file-btn">选择表格文件<input type="file" accept=".xlsx,.xls,.csv,.txt" @change="onSnFile" /></label>
            <button class="btn primary" :disabled="!importWO || !snText.trim()" @click="importSNs">批量导入</button>
          </div>
          <div v-if="fileName" class="mini">已读取：{{ fileName }}（{{ parsedCount }} 条）</div>
        </div>
        <div v-if="importError" class="msg err">{{ importError }}</div>
      </div>
    </div>

    <div v-if="msg" :class="['msg', msgOk ? 'ok' : 'err']">{{ msg }}</div>

    <div class="card">
      <h2>工单列表</h2>
      <div class="field" style="max-width:320px"><input v-model="productFilter" placeholder="按工单号 / 产品筛选" /></div>
      <div class="table-scroll">
      <table>
        <thead><tr><th>工单号</th><th>产品</th><th>批次</th><th>SN 数</th><th>站点序列</th><th>配比</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="w in filteredWos" :key="w.id">
            <td class="mono">{{ w.wo_no }}</td><td>{{ w.product }}</td><td>{{ w.batch }}</td>
            <td>{{ w.plan_qty }}</td><td>{{ (w.stations || []).join(' → ') }}</td><td>{{ w.pack_qty }}</td>
            <td><span :class="['tag', w.status]">{{ w.status }}</span></td>
            <td><button class="btn" @click="viewWO(w.id)">查看 SN</button></td>
          </tr>
          <tr v-if="!wos.length"><td colspan="8" style="text-align:center;color:var(--muted)">暂无工单</td></tr>
        </tbody>
      </table>
      </div>
    </div>

    <div v-if="detail" class="card">
      <h2>{{ detail.wo.wo_no }} · SN 清单</h2>
      <div class="table-scroll">
      <table><thead><tr><th>SN</th><th>当前站</th><th>状态</th><th>不良码</th><th>箱号</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="u in detail.sns" :key="u.id">
            <td class="mono">{{ u.sn }}</td><td>{{ u.current_station || '—' }}</td>
            <td><span :class="['tag', u.state]">{{ u.state }}</span></td>
            <td>{{ u.fail_code || '—' }}</td><td class="mono">{{ u.box_no || '—' }}</td>
            <td><button v-if="u.state === 'failed'" class="btn" @click="rework(u)">返修回当前站</button></td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { dedupe, downloadSnTemplate, normalizeSns, parseSnFile, validateSns } from '../utils/import'

const route = useRoute()

type FlowOption = { key: string; label: string; stations: string[]; source: 'config' | 'history' }

const products = ref<any[]>([])
const productProfiles = ref<any[]>([])
const wos = ref<any[]>([])
const detail = ref<any>(null)
const msg = ref(''); const msgOk = ref(true)
const configuredFlows = ref<FlowOption[]>([])
const selectedFlowKey = ref('')
const selectedStations = ref<string[]>([])
const form = ref({ wo_no: '', product: '', batch: '', plan_qty: 0, pack_qty: 1, location: '戴盟公司', relatedEquipment: [] as string[], relatedPersons: [] as string[] })
const relationOptions = reactive<any>({ equipment: [], persons: [] })
const woNoLoading = ref(false)
let woNoTimer: ReturnType<typeof setTimeout> | null = null
let woNoSeq = 0
const importWO = ref<number | ''>('')
const snText = ref('')
const importMode = ref<'single' | 'batch'>('batch')
const singleSn = ref('')
const fileName = ref('')
const parsedCount = ref(0)
const importError = ref('')
const productFilter = ref('')
const filteredWos = computed(() => {
  const k = productFilter.value.trim().toLowerCase()
  return k ? wos.value.filter(w => `${w.wo_no} ${w.product}`.toLowerCase().includes(k)) : wos.value
})
const hasProductProfile = computed(() => {
  const value = form.value.product
  return productProfiles.value.some(p => [p.code, p.name, p.family].includes(value))
})
const historyFlows = computed<FlowOption[]>(() => {
  const seen = new Set<string>()
  const result: FlowOption[] = []
  wos.value.forEach((wo: any, index: number) => {
    const stations = (wo.stations || []).map((s: any) => String(s || '').trim()).filter(Boolean)
    if (!stations.length) return
    const signature = stations.join('|')
    if (seen.has(signature)) return
    seen.add(signature)
    result.push({ key: `history:${wo.id ?? index}`, label: stations.join(' → '), stations, source: 'history' })
  })
  return result
})
const flowOptions = computed<FlowOption[]>(() => {
  const seen = new Set<string>()
  return [...configuredFlows.value, ...historyFlows.value].filter(flow => {
    const signature = flow.stations.join('|')
    if (seen.has(signature)) return false
    seen.add(signature)
    return true
  })
})
const configFlowOptions = computed(() => flowOptions.value.filter(flow => flow.source === 'config'))
const historyFlowOptions = computed(() => flowOptions.value.filter(flow => flow.source === 'history'))
const woNoReady = computed(() => !!form.value.product && selectedStations.value.length > 0)

async function refreshWoNo() {
  if (!woNoReady.value) {
    form.value.wo_no = ''
    woNoLoading.value = false
    return
  }
  const seq = ++woNoSeq
  woNoLoading.value = true
  try {
    const result = await api.nextWoNo()
    if (seq === woNoSeq && woNoReady.value) form.value.wo_no = result.wo_no
  } catch {
    if (seq === woNoSeq) form.value.wo_no = ''
  } finally {
    if (seq === woNoSeq) woNoLoading.value = false
  }
}

watch(
  [() => form.value.product, () => selectedFlowKey.value],
  () => {
    if (woNoTimer) clearTimeout(woNoTimer)
    woNoTimer = setTimeout(() => void refreshWoNo(), 200)
  },
  { immediate: true },
)

onUnmounted(() => {
  if (woNoTimer) clearTimeout(woNoTimer)
})

function applyFlow() {
  const flow = flowOptions.value.find(item => item.key === selectedFlowKey.value)
  selectedStations.value = flow ? [...flow.stations] : []
}
async function loadConfiguredFlows() {
  try {
    const data: any = await api.woFlowOptions()
    configuredFlows.value = (data.templates || [])
      .map((item: any) => {
        const stations = (item.stations || []).map((station: any) => String(station || '').trim()).filter(Boolean)
        return {
          key: String(item.key || `config:${item.name || ''}`),
          label: `${item.name || '工艺流程'}：${stations.join(' → ')}`,
          stations,
          source: 'config' as const,
        }
      })
      .filter((item: FlowOption) => item.stations.length)
  } catch {
    configuredFlows.value = []
  }
}

function notify(m: string, ok = true) { msg.value = m; msgOk.value = ok; importError.value = '' }
function setImportError(text: string) { importError.value = text; msg.value = '' }
function checkSns(values: string[]): string[] | null {
  const unique = dedupe(values)
  const { valid, invalid } = validateSns(unique)
  if (invalid.length) {
    const preview = invalid.slice(0, 5).join('、')
    const more = invalid.length > 5 ? ` 等 ${invalid.length} 条` : ''
    setImportError(`SN 格式错误：${preview}${more}；要求 16 位大写字母或数字`)
    return null
  }
  return valid
}

async function load() {
  products.value = await api.products()
  try { productProfiles.value = await api.productProfiles() } catch { productProfiles.value = [] }
  if (products.value.length && !form.value.product) form.value.product = products.value[0].name
  wos.value = await api.listWO()
  try {
    const data: any = await api.relationOptions()
    relationOptions.equipment = data.equipment || []
    relationOptions.persons = data.persons || []
  } catch { /* 关联选项加载失败不阻塞建单 */ }
  await loadConfiguredFlows()
  if (selectedFlowKey.value && !flowOptions.value.some(flow => flow.key === selectedFlowKey.value)) {
    selectedFlowKey.value = ''
    selectedStations.value = []
  }
}
onMounted(async () => {
  await load()
  if (route.query.product) productFilter.value = String(route.query.product)
  if (route.query.wo) await viewWO(Number(route.query.wo))
})

async function create() {
  if (!selectedStations.value.length) { notify('请选择已配置流程', false); return }
  try {
    const created: any = await api.createWO({ ...form.value, stations: selectedStations.value })
    notify(`工单创建成功：${created.wo_no || form.value.wo_no}`)
    form.value.wo_no = ''
    form.value.relatedEquipment = []
    form.value.relatedPersons = []
    selectedFlowKey.value = ''
    selectedStations.value = []
    await load()
  } catch (e: any) { notify(e.message, false) }
}

async function importSingle() {
  const sns = checkSns([singleSn.value])
  if (!sns?.length) return
  try {
    const r = await api.importSN(Number(importWO.value), sns)
    notify(`导入 ${r.added} 条，跳过重复 ${r.skipped.length} 条；计划数已更新为 ${r.planQty || 0}`); singleSn.value = ''
    await load(); await viewWO(Number(importWO.value))
  } catch (e: any) { notify(e.message, false) }
}

async function onSnFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const result = await parseSnFile(file)
  if (result.errorMessage) { setImportError(result.errorMessage); input.value = ''; return }
  const checked = checkSns(result.values)
  if (!checked) { input.value = ''; return }
  snText.value = checked.join('\n'); fileName.value = file.name; parsedCount.value = checked.length
  notify(`已从文件解析 ${checked.length} 条 SN，请确认后点击“批量导入”`)
  input.value = ''
}

async function importSNs() {
  const sns = checkSns(normalizeSns(snText.value))
  if (!sns?.length) return
  try {
    const r = await api.importSN(Number(importWO.value), sns)
    notify(`导入 ${r.added} 条，跳过重复 ${r.skipped.length} 条；计划数已更新为 ${r.planQty || 0}`); fileName.value = ''; parsedCount.value = 0
    await load(); await viewWO(Number(importWO.value))
  } catch (e: any) { notify(e.message, false) }
}

async function viewWO(id: number) { detail.value = await api.getWO(id) }
async function rework(u: any) {
  try { await api.rework(detail.value.wo.id, u.sn); notify('已回到当前站重测'); detail.value = await api.getWO(detail.value.wo.id) }
  catch (e: any) { notify(e.message, false) }
}
</script>

<style scoped>
.import-tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--line); margin-bottom: 14px }
.import-tabs button { border: 0; background: transparent; padding: 7px 14px; cursor: pointer; color: var(--muted); font-size: 14px }
.import-tabs button.active { color: var(--red); border-bottom: 2px solid var(--red); font-weight: 600 }
.file-btn { position: relative; overflow: hidden; display: inline-flex; align-items: center }
.file-btn input { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100% }
.flow-preview { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.flow-preview span { display: inline-flex; align-items: center; gap: 5px; border: 1px solid var(--tech-blue-line); background: var(--tech-blue-soft); color: var(--tech-blue); border-radius: 999px; padding: 4px 9px; font-size: 12px; }
.flow-preview b { display: inline-grid; place-items: center; width: 16px; height: 16px; border-radius: 50%; background: var(--tech-blue); color: var(--white); font-size: 10px; }
</style>
