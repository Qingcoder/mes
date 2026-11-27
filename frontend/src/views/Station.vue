<template>
  <div class="station-only">
    <div class="card scan-card">
      <form class="scan-form" @submit.prevent="handleEnter">
        <div class="current-station">
          <span>当前站点</span>
          <b>{{ currentStationLabel }}</b>
          <button class="voice-toggle" :class="{ on: voiceEnabled }" type="button" :aria-pressed="voiceEnabled" @click="toggleVoice">
            {{ voiceEnabled ? '语音已开' : '语音已关' }}
          </button>
        </div>
        <label for="sn-input">SN（扫码枪扫入 / 手动输入后回车或点击确认）</label>
        <div class="sn-row" :class="{ 'no-scan': isDesktop || submitting }">
          <input id="sn-input" ref="snInput" v-model="sn" class="mono sn-input" autocomplete="off" autocapitalize="none" spellcheck="false"
                 placeholder="扫入 SN 后自动匹配工单与站点" :disabled="submitting" />
          <span v-if="!isDesktop" class="sn-scan-icon" :class="{ disabled: submitting }" role="button" tabindex="0"
                :aria-disabled="submitting" title="应用内扫码" aria-label="应用内扫码"
                @click.stop="openStationScanner" @keydown.enter.prevent="openStationScanner" @keydown.space.prevent="openStationScanner"><AppIcon name="scan" :size="18" label="应用内扫码" decorative /></span>
        </div>
        <button class="btn sn-confirm" type="submit" :disabled="snValidating || submitting || !sn.trim()">{{ snValidating ? '校验中…' : '确认 SN' }}</button>

        <div v-if="snValidating" class="mini">正在校验当前人员、站点与工单 SN…</div>

        <div v-if="assignedWo" class="context-strip">
          <span>工单 {{ assignedWo.wo_no }}</span>
          <span>产品 {{ assignedWo.product }}</span>
          <span>操作人 {{ operator }}</span>
          <span>可用站点 {{ stations.length }}</span>
        </div>

        <div class="field judge" style="margin-top:14px"><label>判定（点击即流转）</label>
          <div class="row">
            <button ref="passBtn" type="button" class="btn primary judge-btn" :disabled="!snStatus || !sn || submitting" @click="runStation('pass')">
              {{ submitting ? '流转中…' : '通过' }}
            </button>
            <button type="button" class="btn danger" :disabled="!snStatus || !sn || submitting" @click="result = 'fail'">不良</button>
            <button type="button" class="btn" :disabled="!snStatus || !sn || submitting" @click="openReplace">替换 SN</button>
          </div>
        </div>
        <div v-if="result === 'fail'" class="field fail-panel">
          <label>不良原因码（当前站别，点击即转维修站）</label>
          <div v-if="failCodes.length" class="fail-code-grid">
            <button v-for="c in failCodes" :key="c.code" type="button" class="fail-code-btn"
                    :disabled="!snStatus || !sn || submitting" @click="runStation('fail', c.code)">
              <b>{{ c.code }}</b><span>{{ c.name }}</span>
            </button>
          </div>
          <div v-else class="empty-fail">当前站点未配置不良代码，请先在工艺管理中维护。</div>
        </div>
      </form>

      <div v-if="msg" :class="['msg', ok ? 'ok' : 'err']" style="margin-top:14px">{{ msg }}</div>

      <div v-if="snStatus && activeProduct" class="product-panel">
        <div class="product-head">
          <b>{{ activeProduct.name || activeProduct.code || assignedWo?.product }}</b>
          <span v-if="activeProduct.code" class="mono">{{ activeProduct.code }}</span>
        </div>
        <div class="product-grid">
          <div><label>SN</label><b class="mono">{{ snStatus.sn }}</b></div>
          <div><label>当前站点</label><b>{{ snStatus.stationName || station }}</b></div>
          <div><label>状态</label><b>{{ snStatus.stateText || stateText(snStatus.state) }}</b></div>
          <div><label>左右件</label><b>{{ activeProduct.matchedSide?.name || '未匹配' }}</b></div>
          <div><label>产品系列</label><b>{{ activeProduct.family || '—' }}</b></div>
          <div><label>SN 池</label><b>{{ snPoolCount }} 个</b></div>
        </div>
        <p v-if="activeProduct.description" class="product-desc">{{ activeProduct.description }}</p>
      </div>

      <div v-if="snStatus && snDetail" class="log-panel">
        <div class="log-head">
          <b>SN 详情日志</b>
          <div class="row">
            <span class="mini">来源：{{ snDetail.source === 'remote' ? '线上' : '本地' }}</span>
            <router-link class="link" :to="{ path: '/sn-detail', query: { sn: snStatus.sn } }">查看完整详情</router-link>
          </div>
        </div>
        <div class="mini">工单 {{ snDetail.wo_no || '—' }} · 当前状态 {{ stateText(snDetail.unit?.state) }} · 当前站点 {{ snDetail.unit?.current_station || '—' }}</div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>站点</th><th>结果</th><th>不良代码</th><th>操作人</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="(row, index) in snDetail.records || []" :key="row.id || index">
                <td>{{ row.station || '—' }}</td>
                <td>{{ row.result === 'pass' ? '通过' : '不良' }}</td>
                <td class="mono">{{ row.fail_code || '—' }}</td>
                <td>{{ row.operator || '—' }}</td>
                <td class="mono">{{ fmtTime(row.created_at) }}</td>
              </tr>
              <tr v-if="!(snDetail.records || []).length"><td colspan="5" class="empty">暂无过站日志</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
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
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { AppIcon } from '../components/icons'
import InAppScanner from '../components/InAppScanner.vue'
import { useDesktopMode } from '../utils/device'
import { getVoiceEnabled, setVoiceEnabled, speak, stopSpeak } from '../utils/voice'
import { stationConfigFor, STATION_ROUTE_CONFIG } from '../router/routeConfig'

const route = useRoute()
const { isDesktop } = useDesktopMode()
const stationRouteConfig = computed(() => stationConfigFor(route.path) || STATION_ROUTE_CONFIG)

const assignedWo = ref<any>(null)
const snPoolCount = ref(0)
const woId = ref<number | ''>('')
const stations = ref<string[]>([])
const station = ref(String(stationRouteConfig.value.flowStations?.[0] || ''))
const sn = ref('')
const result = ref<'pass' | 'fail'>('pass')
const failCode = ref('')
const operator = ref('')
const msg = ref(''); const ok = ref(true)
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
const passBtn = ref<HTMLButtonElement | null>(null)
const flow = ref<any[]>([])
const repair = ref<any>(stationRouteConfig.value.repairStation)
const snStatus = ref<any>(null)
const snValidating = ref(false)
const snDetail = ref<any>(null)
const flowResult = ref('')
const flowResultOk = ref(true)
const failCodes = computed(() => flow.value.find(s => s.id === station.value)?.failCodes || [])
const currentStationLabel = computed(() => {
  const step = flow.value.find(s => s.id === station.value)
  if (!step) return station.value || '未分配'
  return step.code && step.code !== step.id ? `${step.name}（${step.code}）` : step.name || step.id
})
const activeProduct = computed(() => snStatus.value?.productDetail || productDetail.value)
const stationScanner = ref<any>(null)
let audioCtx: AudioContext | null = null

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
      msg.value = '当前人员或产品没有配置可用站点，请联系工艺/管理人员关联站点'
      ok.value = false
    }
  } catch (e: any) {
    msg.value = e.message || '工单自动分配失败'; ok.value = false
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
  return map[state] || state || '未知'
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
    nextTick(() => passBtn.value?.focus())
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
    failCode.value = codeValue
    if (!failCode.value) {
      msg.value = '请点击当前站别的不良代码'; ok.value = false; return
    }
  }
  submitting.value = true
  const code = snStatus.value.sn
  try {
    const r: any = await api.unifiedStation({
      sn: code, station: station.value, result: decision,
      fail_code: decision === 'fail' ? failCode.value : undefined,
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
    sn.value = ''; failCode.value = ''; result.value = 'pass'; snDetail.value = null
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
.station-only { max-width: 980px; margin: 0 auto; }
.live-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); margin-left: 6px; vertical-align: middle; }
.scan-form { background: rgba(255,255,255,.03); border: 1px solid var(--line-d); border-radius: 10px; padding: 16px; }
.current-station { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding: 8px 10px; border: 1px solid var(--tech-blue-line); border-radius: 7px; background: var(--tech-blue-soft); }
.current-station span { color: var(--muted); font-size: 11px; }
.current-station b { color: var(--tech-blue); font-size: 14px; }
.sn-row {
  display: grid; grid-template-columns: minmax(0, 1fr) 34px; align-items: center; gap: 6px;
  height: 52px; padding: 0 8px 0 12px; border: 1px solid var(--red); border-radius: 6px;
  background: var(--surface-2); transition: .15s;
}
.sn-row.no-scan { grid-template-columns: minmax(0, 1fr); padding-right: 12px; }
.sn-row:focus-within { box-shadow: 0 0 0 3px rgba(62,123,250,.15); }
.context-strip { display: flex; flex-wrap: wrap; gap: 6px 12px; margin-top: 9px; color: var(--muted); font-size: 12px; }
.context-strip span { border: 1px solid var(--line); border-radius: 999px; padding: 3px 9px; background: #fff; }
.judge .row { flex-wrap: wrap; }
.fail-panel { border-top: 1px dashed var(--line); padding-top: 12px; }
.fail-code-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 7px; margin-top: 8px; }
.fail-code-btn { display: grid; gap: 3px; text-align: left; border: 1px solid var(--red-soft); border-radius: 7px; padding: 8px 10px; background: #fff; color: var(--ink); font-family: inherit; cursor: pointer; }
.fail-code-btn:hover { border-color: var(--red); background: var(--red-soft); }
.fail-code-btn:disabled { opacity: .5; cursor: not-allowed; }
.fail-code-btn b { color: var(--red); font-size: 12px; }
.fail-code-btn span { color: var(--gray); font-size: 11px; line-height: 1.4; }
.empty-fail { border: 1px dashed var(--line); border-radius: 7px; padding: 12px; color: var(--muted); font-size: 12px; margin-top: 8px; }
.product-panel { margin-top: 14px; border: 1px solid var(--tech-blue-line); border-radius: 9px; padding: 13px 14px; background: var(--tech-blue-soft); }
.product-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin-bottom: 10px; }
.product-head b { font-size: 16px; }
.product-head span { color: var(--tech-blue); font-size: 12px; }
.product-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px 14px; }
.product-grid label { display: block; color: var(--muted); font-size: 10px; margin-bottom: 2px; }
.product-grid b { display: block; color: var(--ink); font-size: 12px; overflow-wrap: anywhere; }
.product-desc { margin-top: 10px; color: var(--gray); font-size: 12px; line-height: 1.6; }
.log-panel { margin-top: 14px; border: 1px solid var(--line); border-radius: 9px; padding: 12px 14px; background: rgba(255,255,255,.55); }
.log-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.log-panel .table-scroll { margin-top: 8px; overflow-x: auto; }
.log-panel table { width: 100%; border-collapse: collapse; font-size: 11px; }
.log-panel th, .log-panel td { border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left; white-space: nowrap; }
.log-panel th { color: var(--muted); }
.log-panel .empty { text-align: center; color: var(--muted); padding: 12px; }
.sn-confirm { margin-top: 8px; width: 100%; }
.sn-input {
  width: 100%; min-width: 0; height: 100%; border: 0 !important; padding: 0;
  font-size: 18px !important; letter-spacing: .03em; background: transparent !important;
  box-shadow: none !important; outline: none;
}
input.sn-input:focus { border: 0 !important; box-shadow: none !important; outline: none; }
.sn-scan-icon {
  display: grid; place-items: center; width: 34px; height: 34px; flex: none;
  color: var(--muted); font-size: 18px; line-height: 1; cursor: pointer;
  border-radius: 5px; user-select: none; -webkit-user-select: none;
  -webkit-tap-highlight-color: transparent; touch-action: manipulation;
}
.sn-scan-icon:hover, .sn-scan-icon:focus-visible { color: var(--red); }
.sn-scan-icon:focus-visible { outline: 2px solid var(--red); outline-offset: 1px; }
.sn-scan-icon.disabled { opacity: .35; cursor: not-allowed; }
.assigned-wo { border: 1px solid var(--tech-blue-line); background: var(--tech-blue-soft); border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; }
.assigned-wo label { color: var(--muted); font-size: 12px; margin-bottom: 4px; }
.assigned-main { display: flex; align-items: baseline; gap: 10px; }
.assigned-main b { font-size: 18px; color: var(--ink); }
.assigned-main span { color: var(--gray); font-size: 13px; }
.assigned-wo small { display: block; margin-top: 4px; color: var(--muted); }
.flow-box { border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; background: rgba(255,255,255,.5); }
.flow-box label { color: var(--muted); font-size: 12px; }
.flow-steps { display: flex; align-items: center; gap: 8px; margin: 8px 0 4px; }
.flow-step { padding: 5px 12px; border: 1px solid var(--line); border-radius: 14px; font-size: 13px; }
.flow-step.active { border-color: var(--red); color: var(--red); font-weight: 700; background: var(--red-soft); }
.flow-arrow { color: var(--muted); }
.flow-box small { color: var(--muted); }
.status-box { border: 1px solid var(--tech-blue-line); border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; background: var(--tech-blue-soft); }
.status-title { font-weight: 700; color: var(--tech-blue); margin-bottom: 10px; }
.status-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px 16px; }
.status-grid label { font-size: 11px; color: var(--muted); margin-bottom: 2px; }
.status-grid b { font-size: 13px; color: var(--ink); }
.ok-text { color: var(--green) !important; }
.err-text { color: var(--red) !important; }
.judge-btn { min-width: 160px; }
.recent { margin-top: 18px; }
.recent-list { margin-top: 8px; border: 1px solid var(--line-d); border-radius: 8px; overflow: hidden; }
.recent-item { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-bottom: 1px solid var(--line-d); font-size: 13px; }
.recent-item:last-child { border-bottom: none; }
.recent-item .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.recent-item .dot.ok { background: var(--green); }
.recent-item .dot.bad { background: var(--red); }
.recent-station { color: var(--muted-d); flex: 1; }

/* 过站 / 搜索 模式切换 */
.mode-toggle { display: inline-flex; align-items: center; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; margin-bottom: 14px; }
.mode-toggle button { border: 0; background: #fff; color: var(--muted); padding: 8px 22px; font-size: 14px; font-family: inherit; cursor: pointer; transition: .15s; }
.mode-toggle button + button { border-left: 1px solid var(--line); }
.mode-toggle button.active { background: var(--tech-blue); color: #fff; font-weight: 700; }
.desktop-actions { display: inline-flex; align-items: center; gap: 8px; padding: 0 10px; border-left: 1px solid var(--line); }
.gun-ready { font-size: 12px; color: var(--green); white-space: nowrap; }
.voice-toggle { margin-left: auto; border: 0; border-left: 1px solid var(--line); background: #f6f7f9; color: var(--muted); padding: 8px 12px; font-size: 12px; cursor: pointer; font-family: inherit; }
.modal-mask { position: fixed; inset: 0; z-index: 120; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(4,8,18,.65); }
.modal { width: 100%; max-width: 460px; background: var(--white); border-radius: 10px; padding: 18px; }
.modal h3 { margin-bottom: 8px; }
.modal .field { display: grid; gap: 4px; margin-top: 10px; font-size: 12px; color: var(--muted); }
.modal .field input { width: 100%; }
.modal-foot { display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px; }
.voice-toggle.on { color: var(--tech-blue); background: var(--tech-blue-soft); font-weight: 600; }

/* 搜索模式：紧凑结果列表 */
.search-panel { margin-top: 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; overflow: hidden; max-height: 340px; overflow-y: auto; }
.search-filters { display: flex; gap: 6px; flex-wrap: wrap; padding: 9px 10px; border-bottom: 1px solid var(--line); background: var(--tech-blue-soft); }
.search-filters button { border: 1px solid var(--line); background: #fff; border-radius: 14px; padding: 4px 11px; font-size: 12px; cursor: pointer; font-family: inherit; }
.search-filters button.active { background: var(--red); border-color: var(--red); color: #fff; }
.search-group-title { font-size: 12px; color: var(--muted); padding: 8px 10px 3px; display: flex; justify-content: space-between; }
.search-item { display: flex; width: 100%; align-items: center; justify-content: space-between; gap: 10px; border: 0; background: transparent; border-radius: 6px; padding: 8px 10px; cursor: pointer; text-align: left; font-family: inherit; }
.search-item:hover { background: var(--tech-blue-soft); }
.search-item-main { display: flex; flex-direction: column; min-width: 0; }
.search-item-main b { font-size: 14px; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.search-item-main small { font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.search-badge { font-size: 11px; color: var(--tech-blue); border: 1px solid var(--tech-blue-line); border-radius: 10px; padding: 2px 7px; flex: none; }
.search-state { padding: 18px 10px; text-align: center; color: var(--muted); font-size: 13px; }
.search-state.err { color: var(--red); }

@media (max-width: 768px) {
  .sn-row { height: 50px; padding: 0 6px 0 10px; grid-template-columns: minmax(0, 1fr) 32px; gap: 4px; }
  .sn-row.no-scan { grid-template-columns: minmax(0, 1fr); padding-right: 10px; }
  .sn-input { font-size: 16px !important; }
  .sn-scan-icon { width: 32px; height: 32px; font-size: 17px; }
  .product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .fail-code-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .mode-toggle { width: 100%; }
  .mode-toggle button { flex: 1; padding: 9px 10px; }
  .desktop-actions { display: none; }
}
@media (max-width: 480px) {
  .product-grid, .fail-code-grid { grid-template-columns: 1fr; }
  .judge-btn { width: 100%; }
}
</style>
