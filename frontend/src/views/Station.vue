<template>
  <div class="station-page">
    <!-- ========== 顶栏：品牌 / 工单产品 / 操作员站点 ========== -->
    <header class="st-topbar">
      <div class="st-brand">
        <span class="st-logo">D</span>
        <b>戴盟 MES</b>
      </div>

      <div class="st-wo-pill">
        <AppIcon name="clipboard" :size="16" decorative />
        <span class="st-k">工单</span>
        <b class="mono">{{ woNoLabel }}</b>
        <i class="st-divider" />
        <span class="st-k">产品</span>
        <b class="mono">{{ assignedWo?.product || '—' }}</b>
      </div>

      <div class="st-meta">
        <span class="st-meta-item">
          <AppIcon name="operator" :size="15" decorative />
          <span class="st-k">操作员</span><b>{{ operator || '—' }}</b>
        </span>
        <i class="st-divider" />
        <span class="st-meta-item">
          <AppIcon name="station" :size="15" decorative />
          <span class="st-k">站点</span><b>{{ currentStationLabel }}</b>
        </span>
        <router-link v-if="isAdmin" class="st-backend" to="/dashboard">管理后台</router-link>
      </div>
    </header>

    <main class="st-main">
      <div v-if="error" class="msg err st-msg">{{ error }}</div>
      <div v-if="msg" :class="['msg', ok ? 'ok' : 'err', 'st-msg']">{{ msg }}</div>

      <div class="st-grid">
        <!-- ========== 左：扫码 ========== -->
        <section class="st-card st-scan">
          <h3 class="st-scan-title">扫描或输入 16 位 SN 后回车</h3>
          <form class="st-scan-row" @submit.prevent="handleEnter">
            <AppIcon name="barcode" :size="18" decorative />
            <input
              id="st-sn-input"
              ref="snInput"
              v-model="sn"
              class="mono"
              autocomplete="off"
              autocapitalize="none"
              spellcheck="false"
              placeholder="A1B2C3D4E5F6G7H8"
              :disabled="submitting"
            />
            <button type="submit" class="st-scan-btn" :disabled="submitting || !sn.trim()" aria-label="查询 SN">
              <AppIcon name="search" :size="18" decorative />
            </button>
          </form>

          <p class="st-today">
            今日本站：通过 <b class="ok">{{ stats.passed }}</b> / 不良 <b class="bad">{{ stats.failed }}</b>
            <span v-if="stats.date" class="st-today-date">{{ stats.date }}</span>
          </p>

          <div class="st-art" aria-hidden="true">
            <svg class="st-art-mountain" viewBox="0 0 240 110" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round">
              <path d="M4 106 L50 56 L82 90 L118 40 L168 100 L204 70 L236 106" />
              <path d="M28 106 L70 70 L102 106" />
              <circle cx="206" cy="24" r="9" />
            </svg>
            <svg class="st-art-arm" viewBox="0 0 120 120" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 108h46" />
              <path d="M42 108V80a16 16 0 0 1 16-16h8" />
              <circle cx="68" cy="60" r="8" />
              <path d="M75 53l16-15" />
              <circle cx="96" cy="34" r="6" />
              <path d="M90 40l-7 9M102 39l5 11" />
            </svg>
          </div>
        </section>

        <!-- ========== 中：当前 SN ========== -->
        <section class="st-card st-current">
          <div class="st-card-head">
            <h3 class="st-card-title red">
              <span class="st-disc red"><AppIcon name="check" :size="12" decorative /></span>当前 SN
            </h3>
            <div class="st-head-tools">
              <button class="st-tool" type="button" :class="{ on: voiceEnabled }" :aria-pressed="voiceEnabled" @click="toggleVoice">
                {{ voiceEnabled ? '语音开' : '语音关' }}
              </button>
              <button class="st-tool" type="button" :disabled="!snStatus" @click="openReplace">替换 SN</button>
            </div>
          </div>

          <div class="st-sn-display mono">{{ snStatus?.sn || '—' }}</div>

          <div class="st-hr" />

          <div class="st-field">
            <label>状态</label>
            <span class="st-badge" :class="stateClass">
              <AppIcon v-if="stateClass === 'ok'" name="check" :size="12" decorative />
              <AppIcon v-else-if="stateClass === 'bad'" name="alert" :size="12" decorative />
              {{ stateLabel }}
            </span>
          </div>

          <div class="st-station-box">
            <AppIcon name="station" :size="22" decorative />
            <div>
              <label>当前站</label>
              <b>{{ currentStationLabel }}</b>
            </div>
          </div>

          <div class="st-progress">
            <div class="st-progress-head"><span>{{ doneCount }} / {{ totalCount }} 站</span></div>
            <div class="st-progress-track"><i :style="{ width: progressPercent + '%' }" /></div>
          </div>

          <div class="st-order">订单 {{ woNoLabel }}</div>

          <details v-if="snDetail && (snDetail.records || []).length" class="st-log">
            <summary>过站记录（{{ (snDetail.records || []).length }}）</summary>
            <ul>
              <li v-for="(row, index) in snDetail.records" :key="row.id || index">
                <b>{{ row.station }}</b>
                <span :class="row.result === 'pass' ? 'ok' : 'bad'">{{ row.result === 'pass' ? '通过' : '不良' }}</span>
                <span class="mono">{{ row.fail_code || '' }}</span>
                <small>{{ fmtTime(row.created_at) }}</small>
              </li>
            </ul>
            <router-link class="link" :to="{ path: '/sn-detail', query: { sn: snStatus?.sn } }">查看完整详情</router-link>
          </details>

          <div class="st-dashed"><AppIcon name="lock" :size="15" decorative /></div>
        </section>

        <!-- ========== 右：工序流程 + 不良上报 ========== -->
        <div class="st-right">
          <section class="st-card st-flow">
            <h3 class="st-card-title">
              <span class="st-disc red"><AppIcon name="check" :size="12" decorative /></span>工序流程
            </h3>
            <ul class="st-steps">
              <li v-for="step in steps" :key="step.id" class="st-step" :class="step.state">
                <span class="st-step-icon">
                  <AppIcon v-if="step.state === 'done'" name="circleCheck" :size="20" decorative />
                  <AppIcon v-else-if="step.state === 'failed'" name="alert" :size="20" decorative />
                  <AppIcon v-else-if="step.state === 'repair'" name="wrench" :size="20" decorative />
                  <AppIcon v-else name="clock" :size="20" decorative />
                </span>
                <div class="st-step-main">
                  <b>{{ step.code }}</b>
                  <small>{{ step.hint }}</small>
                </div>
                <AppIcon name="chevronRight" :size="16" decorative />
              </li>
              <li v-if="!steps.length" class="st-empty">当前没有可作业站点</li>
            </ul>
          </section>

          <section class="st-card st-ncr" :class="{ focus: ncrFocused }">
            <h3 class="st-card-title">
              <span class="st-disc red"><AppIcon name="building" :size="12" decorative /></span>不良上报
              <button class="st-close" type="button" aria-label="清空不良上报" @click="resetNcr">✕</button>
            </h3>

            <label>不良代码</label>
            <select v-model="failCode" :disabled="!failCodes.length">
              <option value="">{{ failCodes.length ? '请选择不良代码' : '当前站未配置不良代码' }}</option>
              <option v-for="c in failCodes" :key="c.code" :value="c.code">{{ c.code }}{{ c.name ? ' · ' + c.name : '' }}</option>
            </select>

            <label>备注</label>
            <textarea v-model="remark" maxlength="200" placeholder="请输入备注（选填）" />
            <div class="st-counter">{{ remark.length }} / 200</div>

            <button class="st-submit" type="button" :disabled="!canJudge || submitting || !failCode" @click="runStation('fail')">
              {{ submitting ? '提交中…' : '提交' }}
            </button>
          </section>
        </div>

        <!-- ========== 底部动作 ========== -->
        <div class="st-actions">
          <button class="st-action primary" type="button" :disabled="!canJudge || submitting" @click="runStation('pass')">
            <AppIcon name="check" :size="18" decorative />通过
          </button>
          <button class="st-action ghost" type="button" :disabled="!canJudge || submitting" @click="focusNcr">
            <AppIcon name="alert" :size="18" decorative />不良
          </button>
        </div>
      </div>
    </main>

    <InAppScanner v-if="!isDesktop" ref="stationScanner" @result="onStationScanResult" />

    <div v-if="replaceOpen" class="modal-mask" @click.self="replaceOpen = false">
      <div class="modal replace-modal" role="dialog" aria-modal="true">
        <h3>替换 SN</h3>
        <p class="mini">同一台设备换新标：数量不变，过站记录接续到新 SN，旧 SN 与新 SN 形成替换链可追溯。</p>
        <div class="field"><label>当前 SN</label><input :value="sn" class="mono" readonly /></div>
        <div class="field"><label>新 SN（16 位大写字母或数字）</label><input v-model="replaceNewSn" class="mono" placeholder="如：DAGY31269Q00012D" @keyup.enter="submitReplace" /></div>
        <div class="field"><label>替换原因</label><input v-model="replaceReason" placeholder="如：外壳更换后重新赋码" @keyup.enter="submitReplace" /></div>
        <div v-if="replaceError" class="msg err">{{ replaceError }}</div>
        <div class="modal-foot">
          <button class="btn" type="button" @click="replaceOpen = false">取消</button>
          <button class="btn primary" type="button" :disabled="replaceSaving" @click="submitReplace">{{ replaceSaving ? '处理中…' : '确认替换' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, getUser } from '../api'
import { AppIcon } from '../components/icons'
import InAppScanner from '../components/InAppScanner.vue'
import { useDesktopMode } from '../utils/device'
import { getVoiceEnabled, setVoiceEnabled, speak, stopSpeak } from '../utils/voice'
import { stationConfigFor, STATION_ROUTE_CONFIG } from '../router/routeConfig'

const route = useRoute()
const { isDesktop } = useDesktopMode()
const stationRouteConfig = computed(() => stationConfigFor(route.path) || STATION_ROUTE_CONFIG)
// 管理员在工位界面也能回管理后台；作业员看不到该入口
const isAdmin = computed(() => getUser()?.role === 'admin')

const assignedWo = ref<any>(null)
const snPoolCount = ref(0)
const woId = ref<number | ''>('')
const stations = ref<string[]>([])
const station = ref(String(stationRouteConfig.value.flowStations?.[0] || ''))
const sn = ref('')
const failCode = ref('')
const remark = ref('')
const operator = ref('')
const msg = ref('')
const ok = ref(true)
const error = ref('')
const productDetail = ref<any>(null)
const stat = ref<any>({})
const latest = ref<any>(null)
const recent = ref<{ sn: string; station: string; result: string }[]>([])
const submitting = ref(false)
const sourceLabel = ref('检测中…')
const voiceEnabled = ref(getVoiceEnabled())
const replaceOpen = ref(false)
const replaceNewSn = ref('')
const replaceReason = ref('')
const replaceError = ref('')
const replaceSaving = ref(false)
const pendingStation = ref('')
const snInput = ref<HTMLInputElement | null>(null)
const flow = ref<any[]>([])
const repair = ref<any>(stationRouteConfig.value.repairStation)
const snStatus = ref<any>(null)
const snValidating = ref(false)
const snDetail = ref<any>(null)
const flowResult = ref('')
const flowResultOk = ref(true)
const ncrFocused = ref(false)
const stats = ref({ passed: 0, failed: 0, date: '', stationName: '' })
const stationScanner = ref<any>(null)
let audioCtx: AudioContext | null = null

const failCodes = computed(() => flow.value.find(s => s.id === station.value)?.failCodes || [])
/** 工单号：老数据可能没编号，退回到 #ID，保证工位屏可追溯 */
const woNoLabel = computed(() => {
  const wo = assignedWo.value
  if (!wo) return '—'
  const no = String(wo.wo_no || '').trim()
  return no || (wo.id ? `#${wo.id}` : '未编号')
})
const currentStationLabel = computed(() => {
  const step = flow.value.find(s => s.id === station.value)
  if (!step) return station.value || '未分配'
  return step.code && step.code !== step.id ? `${step.code} ${step.name}` : (step.name || step.id)
})
const activeProduct = computed(() => snStatus.value?.productDetail || productDetail.value)
const canJudge = computed(() => !!snStatus.value && !!sn.value.trim() && !submitting.value)

/** 状态徽章：已通过=绿，待过站=灰，不良=红 */
const stateLabel = computed(() => stateText(snStatus.value?.state || ''))
const stateClass = computed(() => {
  const state = String(snStatus.value?.state || '')
  if (['passed', 'station_done', 'completed', 'packed'].includes(state)) return 'ok'
  if (['failed', 'fail', 'rework', 'hold'].includes(state)) return 'bad'
  return 'idle'
})

/** 工序流程：正常站位按 SN 过站记录判定状态，末尾追加维修站 */
const steps = computed(() => {
  const records: any[] = Array.isArray(snDetail.value?.records) ? snDetail.value.records : []
  const passed = new Set<string>(records.filter((r: any) => r.result === 'pass').map((r: any) => String(r.station)))
  const failed = new Set<string>(records.filter((r: any) => r.result === 'fail').map((r: any) => String(r.station)))
  const list = flow.value.map((item: any) => {
    const id = String(item.id || '')
    const code = String(item.code || id)
    const name = String(item.name || id)
    const hit = (set: Set<string>) => set.has(id) || set.has(code) || set.has(name)
    let state = 'pending'
    let hint = '待过站'
    if (hit(passed)) { state = 'done'; hint = '已通过 ✓' }
    else if (hit(failed)) { state = 'failed'; hint = '不良' }
    return { id, code, name, state, hint }
  })
  const repairId = String(repair.value?.id || '')
  if (repairId) {
    list.push({ id: repairId, code: repairId, name: String(repair.value?.name || '维修站'), state: 'repair', hint: '维修站' })
  }
  return list
})
const doneCount = computed(() => steps.value.filter(s => s.state === 'done').length)
const totalCount = computed(() => flow.value.length || steps.value.length)
const progressPercent = computed(() => {
  if (!totalCount.value) return 0
  return Math.round((doneCount.value / totalCount.value) * 100)
})

function focusSn() { nextTick(() => snInput.value?.focus()) }
function beep(good: boolean) {
  try {
    if (!audioCtx) audioCtx = new AudioContext()
    const o = audioCtx.createOscillator(); const g = audioCtx.createGain()
    o.connect(g); g.connect(audioCtx.destination)
    o.type = 'sine'; o.frequency.value = good ? 880 : 220
    const t = audioCtx.currentTime
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(0.16, t + 0.01)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.18)
    o.start(t); o.stop(t + 0.2)
  } catch { /* 音频不可用时静默降级 */ }
}

async function loadStats() {
  try {
    const data: any = await api.unifiedStationStats(route.path)
    stats.value = {
      passed: Number(data?.passed || 0),
      failed: Number(data?.failed || 0),
      date: String(data?.date || ''),
      stationName: String(data?.stationName || ''),
    }
  } catch { /* 统计失败不阻塞作业 */ }
}

onMounted(async () => {
  void api.unifiedHealth().then((h: any) => {
    sourceLabel.value = h.effective_source === 'remote' ? `线上 ${h.remote.url}` : `本地 ${h.local.url}`
  }).catch(() => { sourceLabel.value = '未知' })
  try {
    const ctx: any = await api.unifiedStationContext(route.path)
    const routeCfg = stationRouteConfig.value
    assignedWo.value = ctx.wo
    snPoolCount.value = ctx.snPoolCount || 0
    productDetail.value = ctx.productDetail || null
    operator.value = ctx.operator || ''
    flow.value = (ctx.flow || []).map((item: any) => ({
      id: String(item.id || item.name || item.code || ''),
      code: String(item.code || ''),
      name: String(item.name || item.id || ''),
      failCodes: item.failCodes || [],
    }))
    repair.value = ctx.repair || routeCfg.repairStation
    stations.value = flow.value.map((item: any) => item.id)
    pendingStation.value = String(route.query.station || '')
    woId.value = Number(ctx.wo.id)
    station.value = stations.value[0] || ''
    if (!stations.value.length) {
      error.value = '当前人员或产品没有配置可用站点，请联系工艺/管理人员关联站点'
    }
    await loadStats()
  } catch (e: any) {
    error.value = e.message || '工单自动分配失败'
  }
  focusSn()
})
onUnmounted(() => {
  if (audioCtx) { audioCtx.close(); audioCtx = null }
  stopSpeak()
})

watch(woId, async (id) => {
  stat.value = {}; recent.value = []
  if (!id) { stations.value = []; return }
  const wanted = pendingStation.value
  station.value = wanted && stations.value.includes(wanted) ? wanted : (stations.value[0] || '')
  pendingStation.value = ''
  stat.value = await api.unifiedQueryWO(Number(id))
  focusSn()
})

function stateText(state: string): string {
  const map: Record<string, string> = {
    pending: '待过站', passed: '已通过', station_done: '本站完成', completed: '已完工',
    fail: '不良', failed: '不良', rework: '维修中', hold: '待维修', packed: '已装箱',
  }
  return map[state] || state || '待过站'
}

function openReplace() {
  replaceNewSn.value = ''
  replaceReason.value = ''
  replaceError.value = ''
  replaceOpen.value = true
}
async function submitReplace() {
  replaceError.value = ''
  const newSn = replaceNewSn.value.trim().toUpperCase()
  if (!newSn) { replaceError.value = '请输入新 SN'; return }
  replaceSaving.value = true
  try {
    const result: any = await api.replaceSn({
      sn: sn.value.trim().toUpperCase(),
      new_sn: newSn,
      station: station.value,
      reason: replaceReason.value,
      operator: operator.value,
    })
    replaceOpen.value = false
    sn.value = result.newSn
    msg.value = `${result.msg || 'SN 已替换'}（过站记录已接续）`
    ok.value = true
    snStatus.value = null
    await validateSnRealtime()
  } catch (e: any) {
    replaceError.value = e.message || '替换失败'
  } finally {
    replaceSaving.value = false
  }
}
function toggleVoice() {
  voiceEnabled.value = !voiceEnabled.value
  setVoiceEnabled(voiceEnabled.value)
  if (!voiceEnabled.value) stopSpeak()
}
function fmtTime(value: string) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}
/** 点底部「不良」→ 聚焦右侧不良上报表单 */
function focusNcr() {
  ncrFocused.value = true
  setTimeout(() => ncrFocused.value = false, 1600)
  nextTick(() => {
    const el = document.querySelector('.st-ncr select') as HTMLSelectElement | null
    el?.focus()
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}
function resetNcr() {
  failCode.value = ''
  remark.value = ''
  ncrFocused.value = false
}

async function validateSnRealtime() {
  const code = sn.value.trim().toUpperCase()
  sn.value = code
  snStatus.value = null
  snDetail.value = null
  flowResult.value = ''
  if (!code || code.length < 16 || submitting.value) {
    msg.value = '不是这个SN：SN 应为 16 位大写字母或数字'; ok.value = false; beep(false)
    return
  }
  snValidating.value = true
  try {
    const match: any = await api.unifiedResolveSn(code, route.path)
    station.value = match.station || station.value
    const step = flow.value.find(s => s.id === station.value)
    snStatus.value = {
      ...match,
      stateText: stateText(match.state),
      stationName: match.matched?.stationName || step?.name || match.stationName || station.value,
      productDetail: match.productDetail || productDetail.value,
    }
    try { snDetail.value = await api.unifiedQuerySn(code, match.source || '') } catch { snDetail.value = null }
    flowResult.value = '人员 / 站点 / SN 匹配，待判定'; flowResultOk.value = true
    msg.value = `SN ${code} 校验通过：当前人员、站点与工单 SN 池均匹配`; ok.value = true
    localStorage.setItem('mes_last_sn', code)
  } catch (e: any) {
    msg.value = `不是这个SN：${e.message || '当前人员、站点或工单 SN 池不匹配'}`; ok.value = false; beep(false)
  } finally { snValidating.value = false }
}

async function handleEnter() {
  if (!sn.value.trim()) return
  await validateSnRealtime()
}

async function runStation(decision: 'pass' | 'fail', codeValue = '') {
  if (submitting.value || !snStatus.value || !sn.value.trim()) return
  if (decision === 'fail') {
    failCode.value = codeValue || failCode.value
    if (!failCode.value) {
      msg.value = '请选择不良代码后再提交'; ok.value = false
      focusNcr()
      return
    }
  }
  submitting.value = true
  const code = snStatus.value.sn
  try {
    const r: any = await api.unifiedStation({
      sn: code, station: station.value, result: decision,
      fail_code: decision === 'fail' ? failCode.value : undefined,
      remark: decision === 'fail' ? (remark.value || '').trim() : undefined,
      operator: operator.value,
    }, route.path)
    if (r.source) sourceLabel.value = r.source === 'remote' ? `线上 http://10.30.120.18:8080` : '本地 8007'
    flowResult.value = decision === 'pass' ? '合格 · 已流转至下一站' : '不合格 · 已转入维修站'
    flowResultOk.value = decision === 'pass'
    msg.value = (r.msg || '流转成功') + (r.source ? `（${r.source}）` : ''); ok.value = true
    const repairName = r.repairStation?.name || repair.value?.name || '维修站'
    if (isDesktop.value) speak(decision === 'pass' ? '通过' : 'NG')
    snStatus.value.state = r.state || snStatus.value.state
    snStatus.value.stateText = stateText(snStatus.value.state)
    if (decision === 'fail') {
      snStatus.value.stationName = repairName
      snStatus.value.currentStation = r.currentStation || repairName
    }
    latest.value = { sn: code, station: station.value, result: decision }
    recent.value.unshift({ sn: code, station: station.value, result: decision })
    if (recent.value.length > 6) recent.value.pop()
    beep(decision === 'pass')
    sn.value = ''; failCode.value = ''; remark.value = ''; snDetail.value = null
    await loadStats()
  } catch (e: any) {
    msg.value = e.message; ok.value = false; beep(false)
  }
  finally { submitting.value = false; focusSn() }
}

function openStationScanner() {
  if (isDesktop.value) return
  stationScanner.value?.open()
}

async function onStationScanResult(payload: { text: string; format: string }) {
  const code = (payload?.text || '').trim()
  if (!code) return
  sn.value = code
  beep(true)
  focusSn()
  msg.value = `已识别 ${code}，正在自动匹配 SN 池…`; ok.value = true
  await validateSnRealtime()
}
</script>

<style scoped>
/* ============ 设计变量（对齐参考图） ============ */
.station-page {
  --st-bg: #f3f4f6;
  --st-card: #fff;
  --st-radius: 14px;
  --st-top: #0e1a2b;
  --st-top-2: #16243a;
  --st-red: var(--red);
  --st-green: #16a34a;
  --st-ink: var(--ink);
  --st-muted: var(--muted);
  --st-line: var(--line);
  min-height: 100%;
  background:
    radial-gradient(circle at 12% 8%, rgba(230,23,54,.05), transparent 42%),
    radial-gradient(circle at 88% 92%, rgba(46,111,232,.05), transparent 45%),
    var(--st-bg);
}

/* ============ 顶栏 ============ */
.st-topbar {
  display: flex; align-items: center; gap: 16px;
  height: 56px; padding: 0 18px;
  background: linear-gradient(180deg, var(--st-top-2), var(--st-top));
  color: #fff; position: sticky; top: 0; z-index: 20;
  box-shadow: 0 2px 14px rgba(10,11,13,.35);
}
.st-brand { display: flex; align-items: center; gap: 10px; flex: none; }
.st-logo {
  width: 30px; height: 30px; border-radius: 8px; background: var(--st-red);
  display: grid; place-items: center; font-weight: 800; font-size: 16px; color: #fff;
  box-shadow: 0 0 12px rgba(230,23,54,.5);
}
.st-brand b { font-size: 17px; letter-spacing: .02em; }
.st-wo-pill {
  display: flex; align-items: center; gap: 8px; flex: 0 1 auto; min-width: 0;
  margin: 0 auto; padding: 7px 16px; border-radius: 999px;
  background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.14);
  color: rgba(255,255,255,.72); font-size: 13px; white-space: nowrap; overflow: hidden;
}
.st-wo-pill b { color: #fff; font-size: 13px; }
.st-k { color: rgba(255,255,255,.55); }
.st-divider { width: 1px; height: 16px; background: rgba(255,255,255,.22); display: inline-block; }
.st-meta { display: flex; align-items: center; gap: 10px; flex: none; font-size: 13px; }
.st-meta-item { display: flex; align-items: center; gap: 6px; color: rgba(255,255,255,.6); }
.st-meta-item b { color: #fff; }
.st-backend {
  margin-left: 4px; border: 1px solid rgba(255,255,255,.22); border-radius: 999px;
  padding: 3px 10px; font-size: 11px; color: rgba(255,255,255,.75); text-decoration: none; white-space: nowrap;
}
.st-backend:hover { background: rgba(255,255,255,.12); color: #fff; }

/* ============ 主区 ============ */
.st-main { padding: 18px 20px 24px; }
.st-msg { margin-bottom: 12px; }
.st-grid {
  display: grid;
  grid-template-columns: minmax(300px, 1.05fr) minmax(280px, 1fr) minmax(280px, .95fr);
  grid-template-areas: "scan current right" "actions actions right";
  gap: 16px; align-items: start;
}
.st-scan { grid-area: scan; }
.st-current { grid-area: current; }
.st-right { grid-area: right; display: grid; gap: 14px; }
/* 底部动作与上方两张卡片等宽对齐（通过=左卡宽，不良=中卡宽） */
.st-actions {
  grid-area: actions; display: grid;
  grid-template-columns: minmax(300px, 1.05fr) minmax(280px, 1fr);
  gap: 16px;
}

/* ============ 卡片 ============ */
.st-card {
  background: var(--st-card); border: 1px solid var(--st-line); border-radius: var(--st-radius);
  padding: 18px; box-shadow: 0 2px 10px rgba(20,24,31,.05);
}
.st-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.st-card-title {
  display: flex; align-items: center; gap: 8px; margin: 0 0 14px;
  font-size: 15px; font-weight: 700; color: var(--st-ink);
}
.st-card-title.red { color: var(--st-red); }
.st-card-head .st-card-title { margin-bottom: 10px; }
.st-disc {
  width: 18px; height: 18px; border-radius: 50%; display: inline-grid; place-items: center;
  background: var(--st-red); color: #fff; flex: none;
}
.st-head-tools { display: flex; gap: 6px; }
.st-tool {
  border: 1px solid var(--st-line); background: #fff; color: var(--st-muted);
  border-radius: 6px; padding: 3px 9px; font-size: 11px; cursor: pointer; font-family: inherit;
}
.st-tool:hover { border-color: var(--st-red); color: var(--st-red); }
.st-tool.on { background: var(--red-soft); border-color: var(--red); color: var(--st-red); }
.st-tool:disabled { opacity: .45; cursor: not-allowed; }

/* ============ 左：扫码 ============ */
.st-scan { position: relative; overflow: hidden; min-height: 300px; display: flex; flex-direction: column; }
.st-scan-title { margin: 0 0 16px; text-align: center; font-size: 15px; font-weight: 600; color: var(--st-ink); }
.st-scan-row {
  display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 10px;
  height: 52px; padding: 0 6px 0 14px;
  border: 2px solid var(--st-red); border-radius: 10px; background: #fff;
  box-shadow: 0 0 0 4px rgba(230,23,54,.08); transition: box-shadow .15s, border-color .15s;
}
.st-scan-row:focus-within { box-shadow: 0 0 0 6px rgba(230,23,54,.14); }
.st-scan-row > .app-icon { color: var(--st-red); }
.st-scan-row input {
  width: 100%; min-width: 0; height: 100%; border: 0 !important; padding: 0; background: transparent !important;
  box-shadow: none !important; outline: none; font-size: 19px; letter-spacing: .04em; color: var(--st-ink);
}
.st-scan-btn {
  width: 38px; height: 38px; border: 0; border-radius: 8px; background: var(--st-red); color: #fff;
  display: grid; place-items: center; cursor: pointer; transition: background .15s, transform .1s;
}
.st-scan-btn:hover:not(:disabled) { background: var(--red-hover); }
.st-scan-btn:active:not(:disabled) { transform: scale(.94); }
.st-scan-btn:disabled { opacity: .5; cursor: not-allowed; }
.st-today { margin: 14px 0 0; text-align: center; font-size: 13px; color: var(--st-muted); }
.st-today b.ok { color: var(--st-green); font-weight: 700; }
.st-today b.bad { color: var(--st-red); font-weight: 700; }
.st-today-date { margin-left: 6px; font-size: 11px; }
.st-art { position: absolute; inset: auto 0 0 0; height: 132px; pointer-events: none; opacity: .9; }
.st-art-mountain { position: absolute; left: 4%; bottom: 0; width: 62%; color: rgba(120,128,140,.35); }
.st-art-arm { position: absolute; right: 6%; bottom: 4px; width: 27%; color: rgba(230,23,54,.75); }

/* ============ 中：当前 SN ============ */
.st-current { display: flex; flex-direction: column; }
.st-sn-display {
  font-size: 26px; font-weight: 700; letter-spacing: .04em; color: var(--st-ink);
  text-align: center; padding: 6px 0 12px; word-break: break-all;
}
.st-hr { height: 1px; background: var(--st-line); margin-bottom: 14px; }
.st-field { margin-bottom: 12px; }
.st-field label, .st-ncr label { display: block; font-size: 12px; color: var(--st-muted); margin-bottom: 6px; }
.st-badge {
  display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; padding: 4px 12px;
  font-size: 12px; font-weight: 600; background: #f0f2f5; color: var(--gray);
}
.st-badge.ok { background: #e7f7ed; color: var(--st-green); }
.st-badge.bad { background: var(--red-soft); color: var(--st-red); }
.st-station-box {
  display: flex; align-items: center; gap: 12px; border: 1px solid var(--st-line); border-radius: 10px;
  padding: 10px 14px; margin-bottom: 14px; background: #fafbfc;
}
.st-station-box .app-icon { color: var(--st-red); }
.st-station-box label { display: block; font-size: 11px; color: var(--st-muted); }
.st-station-box b { font-size: 17px; color: var(--st-ink); }
.st-progress { margin-bottom: 12px; }
.st-progress-head { font-size: 12px; color: var(--st-muted); margin-bottom: 6px; }
.st-progress-track { height: 8px; border-radius: 999px; background: #eceef1; overflow: hidden; }
.st-progress-track i {
  display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, #ff5a72, var(--st-red)); transition: width .3s;
}
.st-order { text-align: center; font-size: 12px; color: var(--st-muted); }
.st-dashed {
  display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 10px;
  color: rgba(230,23,54,.65);
}
.st-dashed::before, .st-dashed::after {
  content: ''; flex: 1; border-top: 1px dashed rgba(230,23,54,.45);
}
.st-log { margin-top: 12px; border-top: 1px dashed var(--st-line); padding-top: 10px; }
.st-log summary { font-size: 12px; color: var(--st-muted); cursor: pointer; }
.st-log ul { list-style: none; margin: 8px 0; padding: 0; display: grid; gap: 5px; }
.st-log li { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--gray); }
.st-log li b { color: var(--st-ink); }
.st-log li .ok { color: var(--st-green); }
.st-log li .bad { color: var(--st-red); }
.st-log li small { margin-left: auto; color: var(--st-muted); font-size: 11px; }

/* ============ 右：工序流程 ============ */
.st-steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.st-step {
  display: flex; align-items: center; gap: 12px; border: 1px solid var(--st-line);
  border-radius: 10px; padding: 10px 12px; transition: border-color .15s, background .15s;
}
.st-step.done { border-color: #b7e6c7; background: #f1fbf4; }
.st-step.failed { border-color: #f5c2c9; background: #fef6f7; }
.st-step-icon { display: inline-flex; flex: none; color: var(--st-muted); }
.st-step.done .st-step-icon { color: var(--st-green); }
.st-step.failed .st-step-icon { color: var(--st-red); }
.st-step-main { flex: 1; min-width: 0; }
.st-step-main b { display: block; font-size: 14px; color: var(--st-ink); }
.st-step-main small { font-size: 11px; color: var(--st-muted); }
.st-step.done .st-step-main small { color: var(--st-green); }
.st-step > .app-icon:last-child { color: #c3c8ce; }
.st-empty { font-size: 12px; color: var(--st-muted); padding: 10px 0; }

/* ============ 右：不良上报 ============ */
.st-ncr { transition: box-shadow .2s, border-color .2s; }
.st-ncr.focus { border-color: var(--st-red); box-shadow: 0 0 0 4px rgba(230,23,54,.12); }
.st-ncr .st-card-title { margin-bottom: 12px; }
.st-close {
  margin-left: auto; border: 0; background: transparent; color: var(--st-muted);
  font-size: 15px; cursor: pointer; line-height: 1; padding: 2px 4px; border-radius: 4px;
}
.st-close:hover { color: var(--st-ink); background: #f0f2f5; }
.st-ncr select {
  width: 100%; height: 38px; border: 1px solid var(--st-line); border-radius: 8px; padding: 0 10px;
  background: #fff; font-size: 13px; color: var(--st-ink); margin-bottom: 12px;
}
.st-ncr select:focus { outline: none; border-color: var(--st-red); box-shadow: 0 0 0 3px rgba(230,23,54,.1); }
.st-ncr textarea {
  width: 100%; min-height: 74px; resize: vertical; border: 1px solid var(--st-line); border-radius: 8px;
  padding: 9px 10px; font-size: 13px; font-family: inherit; color: var(--st-ink);
}
.st-ncr textarea:focus { outline: none; border-color: var(--st-red); box-shadow: 0 0 0 3px rgba(230,23,54,.1); }
.st-counter { text-align: right; font-size: 11px; color: var(--st-muted); margin: 4px 0 12px; }
.st-submit {
  width: 100%; height: 44px; border: 0; border-radius: 10px; background: var(--st-red); color: #fff;
  font-size: 15px; font-weight: 600; cursor: pointer; transition: background .15s, transform .1s;
}
.st-submit:hover:not(:disabled) { background: var(--red-hover); }
.st-submit:active:not(:disabled) { transform: translateY(1px); }
.st-submit:disabled { opacity: .5; cursor: not-allowed; }

/* ============ 底部动作 ============ */
.st-action {
  height: 54px; border-radius: 12px; font-size: 17px; font-weight: 700; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; gap: 10px;
  transition: background .15s, transform .1s, box-shadow .15s;
}
.st-action.primary {
  border: 0; background: linear-gradient(180deg, #f5334f, var(--st-red)); color: #fff;
  box-shadow: 0 6px 16px rgba(230,23,54,.28);
}
.st-action.primary:hover:not(:disabled) { background: var(--red-hover); box-shadow: 0 8px 20px rgba(230,23,54,.34); }
.st-action.primary:active:not(:disabled) { transform: translateY(1px); }
.st-action.ghost {
  border: 1px solid var(--st-line); background: #fff; color: var(--st-ink);
  box-shadow: 0 2px 8px rgba(20,24,31,.05);
}
.st-action.ghost:hover:not(:disabled) { border-color: var(--st-red); color: var(--st-red); }
.st-action:disabled { opacity: .55; cursor: not-allowed; box-shadow: none; }

/* ============ 响应式 ============ */
@media (max-width: 1180px) {
  .st-grid {
    grid-template-columns: minmax(280px, 1fr) minmax(280px, 1fr);
    grid-template-areas: "scan current" "actions actions" "right right";
  }
  .st-right { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 860px) {
  .st-topbar { height: auto; flex-wrap: wrap; gap: 8px 12px; padding: 10px 14px; }
  .st-wo-pill { order: 3; width: 100%; margin: 0; justify-content: center; }
  .st-meta { margin-left: auto; }
  .st-grid {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas: "scan" "current" "actions" "right";
  }
  .st-right { grid-template-columns: minmax(0, 1fr); }
  .st-actions { grid-template-columns: 1fr; }
  .st-action { height: 50px; }
  .st-main { padding: 14px 12px 20px; }
  .st-sn-display { font-size: 21px; }
}
</style>  
