<template>
  <div class="quality-dashboard">
    <div class="head">
      <div>
        <h2>质量看板</h2>
        <p class="sub">实时汇总在制状态、良品率、不良类型与过程能力，帮助质量人员快速定位主要问题。</p>
      </div>
      <div class="row">
        <span class="live"><i></i>30 秒自动刷新</span>
        <button class="btn" type="button" :disabled="loading" @click="load">{{ loading ? '刷新中…' : '刷新' }}</button>
        <button class="btn" type="button" @click="router.push('/')">返回首页</button>
      </div>
    </div>

    <div v-if="error" class="msg err">{{ error }}</div>
    <div v-else-if="loading && !data" class="msg">加载质量看板…</div>

    <template v-else-if="data">
      <div class="updated">更新时间：{{ formatTime(data.generatedAt) }}</div>

      <div v-if="!data.quality.hasData" class="data-banner">
        <b>当前没有过站记录</b>
        <span>良品率、不良率与 CPK 会在扫码过站后自动计算；WIP 状态仍按当前 SN 展示。</span>
      </div>

      <div class="kpi-grid">
        <section class="card kpi primary">
          <span>WIP 在制数量</span>
          <b>{{ data.wip.total }}</b>
          <small>共 {{ data.wip.unitTotal }} 个 SN，未包装计入在制</small>
        </section>
        <section class="card kpi good">
          <span>良品率</span>
          <b>{{ data.quality.goodRate }}<em>%</em></b>
          <small>通过 {{ data.quality.passed }} / 过站 {{ data.quality.checks }}</small>
        </section>
        <section class="card kpi bad">
          <span>不良品率</span>
          <b>{{ data.quality.defectRate }}<em>%</em></b>
          <small>不良 {{ data.quality.failed }} / 返修 {{ data.quality.reworked }}</small>
        </section>
        <section class="card kpi">
          <span>CPK 估算</span>
          <b :class="{ warn: data.quality.cpk < data.quality.cpkTarget && data.quality.hasData }">
            {{ data.quality.hasData ? data.quality.cpk : '—' }}
          </b>
          <small>目标 ≥ {{ data.quality.cpkTarget }} · {{ data.quality.cpkLevel }}</small>
        </section>
      </div>

      <div class="split-grid">
        <section class="card">
          <div class="panel-head"><div><b>WIP 状态分布</b><p class="mini">按 SN 当前状态统计</p></div></div>
          <div v-if="wipStatuses.length" class="wip-body">
            <div class="donut-wrap">
              <svg viewBox="0 0 120 120" role="img" aria-label="WIP状态分布">
                <circle cx="60" cy="60" r="46" pathLength="100" class="donut-track" />
                <circle
                  v-for="item in statusArcs" :key="item.key"
                  cx="60" cy="60" r="46" pathLength="100" class="donut-arc"
                  :stroke="item.color"
                  :stroke-dasharray="item.dash"
                  :stroke-dashoffset="item.offset"
                />
              </svg>
              <div class="donut-center"><b>{{ data.wip.total }}</b><span>在制 SN</span></div>
            </div>
            <div class="status-list">
              <div v-for="item in wipStatuses" :key="item.key" class="status-row">
                <span class="dot" :class="'s-' + item.key"></span>
                <b>{{ item.name }}</b>
                <div class="progress"><i :class="'s-' + item.key" :style="{ width: item.ratio + '%' }"></i></div>
                <strong>{{ item.count }}</strong>
                <small>{{ item.ratio }}%</small>
              </div>
            </div>
          </div>
          <div v-else class="empty">暂无 WIP 数据</div>
        </section>

        <section class="card">
          <div class="panel-head"><div><b>质量结果概览</b><p class="mini">来自已采集过站记录</p></div></div>
          <div class="result-grid">
            <div><span>过站次数</span><b>{{ data.quality.checks }}</b></div>
            <div><span>通过</span><b class="green">{{ data.quality.passed }}</b></div>
            <div><span>不良</span><b class="red">{{ data.quality.failed }}</b></div>
            <div><span>返修</span><b class="amber">{{ data.quality.reworked }}</b></div>
            <div><span>涉及 SN</span><b>{{ data.quality.recordedUnits }}</b></div>
            <div><span>不良总数</span><b>{{ data.defects.total }}</b></div>
          </div>
          <p class="note">{{ data.note }}</p>
        </section>
      </div>

      <section class="card">
        <div class="panel-head">
          <div><b>不良类型柏拉图</b><p class="mini">柱形为不良数量，折线为累计占比；按数量降序排列</p></div>
          <span v-if="topDefect" class="focus">首要问题：{{ topDefect.name }}（{{ topDefect.count }} 次 / {{ topDefect.ratio }}%）</span>
        </div>
        <div v-if="pareto.length" class="chart-wrap">
          <svg :viewBox="`0 0 ${paretoWidth} ${paretoHeight}`" role="img" aria-label="不良类型柏拉图">
            <g v-for="line in paretoGrid" :key="line.value">
              <line :x1="chartLeft" :x2="paretoWidth - 24" :y1="line.y" :y2="line.y" class="grid-line" />
              <text :x="chartLeft - 8" :y="line.y + 4" text-anchor="end" class="axis-label">{{ line.value }}%</text>
            </g>
            <line :x1="chartLeft" :x2="paretoWidth - 24" :y1="pareto80Y" :y2="pareto80Y" class="pareto80-line" />
            <text :x="paretoWidth - 28" :y="pareto80Y - 5" text-anchor="end" class="axis-label">80% 参考线</text>
            <rect
              v-for="item in pareto" :key="item.code"
              :x="item.x" :y="item.y" :width="item.width" :height="item.height"
              :class="item.rank <= 2 ? 'bar hot' : 'bar'"
            >
              <title>{{ item.name }}：{{ item.count }} 次，占比 {{ item.ratio }}%</title>
            </rect>
            <polyline :points="paretoLine" class="pareto-line" />
            <circle v-for="point in paretoPoints" :key="'p-' + point.code" :cx="point.x" :cy="point.y" r="3.5" class="pareto-dot">
              <title>累计 {{ point.cumulativeRatio }}%</title>
            </circle>
            <text v-for="item in pareto" :key="'t-' + item.code" :x="item.x + item.width / 2" :y="paretoHeight - 10" text-anchor="middle" class="axis-label">{{ short(item.name, 8) }}</text>
          </svg>
        </div>
        <div v-else class="empty">暂无不良记录</div>
      </section>

      <div class="split-grid bottom">
        <section class="card">
          <div class="panel-head"><div><b>不良类型排名</b><p class="mini">按发生次数排序，显示占比</p></div></div>
          <div v-if="defects.length" class="bar-list">
            <div v-for="item in defects.slice(0, 8)" :key="item.code" class="bar-item">
              <span class="bar-rank">{{ item.rank }}</span>
              <div class="bar-copy">
                <div><b>{{ item.name }}</b><small>{{ item.count }} 次 · {{ item.ratio }}%</small></div>
                <div class="bar-track"><i :style="{ width: Math.max(item.ratio, 2) + '%' }"></i></div>
              </div>
            </div>
          </div>
          <div v-else class="empty">暂无不良记录</div>
        </section>

        <section class="card">
          <div class="panel-head"><div><b>CPK 趋势</b><p class="mini">近 7 日过程能力估算变化</p></div><span class="target">目标线 {{ data.quality.cpkTarget }}</span></div>
          <div v-if="hasTrendData" class="chart-wrap trend">
            <svg :viewBox="`0 0 ${trendWidth} ${trendHeight}`" role="img" aria-label="CPK趋势图">
              <g v-for="line in trendGrid" :key="line.value">
                <line :x1="chartLeft" :x2="trendWidth - 20" :y1="line.y" :y2="line.y" class="grid-line" />
                <text :x="chartLeft - 8" :y="line.y + 4" text-anchor="end" class="axis-label">{{ line.value }}</text>
              </g>
              <line :x1="chartLeft" :x2="trendWidth - 20" :y1="targetY" :y2="targetY" class="target-line" />
              <polyline :points="trendLine" class="trend-line" />
              <g v-for="point in trendPoints" :key="point.date">
                <circle :cx="point.x" :cy="point.y" r="3.5" :class="point.hasData ? 'trend-dot' : 'trend-dot empty-dot'">
                  <title>{{ point.label }}：{{ point.hasData ? point.cpk : '无数据' }}</title>
                </circle>
                <text :x="point.x" :y="trendHeight - 8" text-anchor="middle" class="axis-label">{{ point.label }}</text>
              </g>
            </svg>
          </div>
          <div v-else class="empty">暂无过站数据，CPK 趋势将在采集后显示</div>
          <p class="note">CPK 由过站一次通过率折算，用于发现趋势变化，不替代测量数据计算的过程能力。</p>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const data = ref<any>(null)
const loading = ref(false)
const error = ref('')
let timer: number | undefined

const statuses = computed<any[]>(() => data.value?.wip?.statuses || [])
const wipStatuses = computed<any[]>(() => {
  const rows = statuses.value.filter(item => item.key !== 'packed' && Number(item.count) > 0)
  const total = data.value?.wip?.total || 0
  return rows.map(item => ({ ...item, ratio: total ? Math.round(Number(item.count) * 1000 / total) / 10 : 0 }))
})
const statusColors: Record<string, string> = {
  pending: '#7D96B6', passed: '#1A7A4C', station_done: '#2E6FE8',
  rework: '#C77700', failed: '#E61736', packed: '#5C6470',
}
const statusArcs = computed(() => {
  let offset = 0
  return wipStatuses.value.map(item => {
    const ratio = Number(item.ratio) || 0
    const arc = { ...item, color: statusColors[item.key] || '#8C9199', dash: `${ratio} ${100 - ratio}`, offset: -offset }
    offset += ratio
    return arc
  })
})
const defects = computed<any[]>(() => data.value?.defects?.items || [])
const trend = computed<any[]>(() => data.value?.trend || [])
const topDefect = computed<any>(() => defects.value[0] || null)
const hasTrendData = computed(() => trend.value.some(item => item.hasData))

const paretoWidth = 760
const paretoHeight = 280
const chartLeft = 42
const paretoTop = 18
const chartHeight = 220
const paretoGrid = [0, 25, 50, 75, 100].map(value => ({
  value,
  y: paretoTop + chartHeight - value / 100 * chartHeight,
}))
const pareto = computed(() => {
  const items = defects.value.slice(0, 8)
  const max = Math.max(1, ...items.map(item => Number(item.count) || 0))
  const slot = (paretoWidth - chartLeft - 24) / Math.max(items.length, 1)
  return items.map((item, index) => {
    const height = (Number(item.count) || 0) / max * chartHeight
    const x = chartLeft + index * slot + slot * 0.18
    return {
      ...item,
      x,
      y: paretoTop + chartHeight - height,
      width: slot * 0.64,
      height,
      cx: x + slot * 0.32,
      lineY: paretoTop + chartHeight - (Number(item.cumulativeRatio) || 0) / 100 * chartHeight,
    }
  })
})
const paretoLine = computed(() => pareto.value.map(item => `${item.cx},${item.lineY}`).join(' '))
const paretoPoints = computed(() => pareto.value.map(item => ({ code: item.code, x: item.cx, y: item.lineY, cumulativeRatio: item.cumulativeRatio })))
const pareto80Y = paretoTop + chartHeight - 80 / 100 * chartHeight

const trendWidth = 520
const trendHeight = 220
const trendTop = 18
const trendChartHeight = 160
const trendGrid = [0, 0.5, 1.0, 1.5, 2.0, 2.5].map(value => ({
  value,
  y: trendTop + trendChartHeight - value / 2.5 * trendChartHeight,
}))
const targetY = computed(() => trendTop + trendChartHeight - (data.value?.quality?.cpkTarget || 1.33) / 2.5 * trendChartHeight)
const trendPoints = computed(() => {
  const items = trend.value
  const slot = (trendWidth - chartLeft - 20) / Math.max(items.length - 1, 1)
  return items.map((item, index) => ({
    ...item,
    x: chartLeft + index * slot,
    y: trendTop + trendChartHeight - Math.min(Number(item.cpk) || 0, 2.5) / 2.5 * trendChartHeight,
  }))
})
const trendLine = computed(() => trendPoints.value.map(item => `${item.x},${item.y}`).join(' '))

function short(value: string, max: number) {
  const text = String(value || '')
  return text.length > max ? text.slice(0, max) + '…' : text
}
function formatTime(value: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}
async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    data.value = await api.qualityDashboard()
  } catch (e: any) {
    error.value = e.message || '质量看板加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
  timer = window.setInterval(() => { void load() }, 30000)
})
onUnmounted(() => { if (timer) window.clearInterval(timer) })
</script>

<style scoped>
.quality-dashboard { display: grid; gap: 14px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.head .row { display: flex; align-items: center; gap: 8px; }
.live { color: var(--muted); font-size: 12px; display: inline-flex; align-items: center; gap: 6px; }
.live i { width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 3px var(--green-soft); }
.updated { color: var(--muted); font-size: 11px; text-align: right; margin-top: -8px; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.kpi { display: grid; gap: 5px; border-top: 2px solid var(--line); }
.kpi.primary { border-top-color: var(--tech-blue); }
.kpi.good { border-top-color: var(--green); }
.kpi.bad { border-top-color: var(--red); }
.kpi > span { color: var(--muted); font-size: 12px; }
.kpi > b { font-size: 30px; line-height: 1.1; }
.kpi > b.warn { color: var(--amber); }
.kpi em { font-style: normal; font-size: 15px; margin-left: 2px; }
.kpi small { color: var(--muted); font-size: 11px; }
.split-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.mini { color: var(--muted); font-size: 11px; margin-top: 3px; }
.focus { color: var(--red); font-size: 11px; font-weight: 600; }
.target { color: var(--muted); font-size: 11px; }
.wip-body { display: grid; grid-template-columns: 132px minmax(0, 1fr); gap: 14px; align-items: center; margin-top: 8px; }
.donut-wrap { position: relative; width: 132px; height: 132px; }
.donut-wrap svg { width: 100%; height: 100%; display: block; }
.donut-track { fill: none; stroke: var(--bg); stroke-width: 12; }
.donut-arc { fill: none; stroke-width: 12; transform: rotate(-90deg); transform-origin: 60px 60px; }
.donut-center { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; }
.donut-center b { font-size: 22px; line-height: 1.1; }
.donut-center span { color: var(--muted); font-size: 10px; margin-top: 3px; }
.status-strip { display: flex; gap: 2px; height: 12px; margin: 14px 0; }
.status-strip i, .dot, .progress i { background: var(--muted); }
.status-strip .s-pending, .dot.s-pending, .progress i.s-pending { background: #7D96B6; }
.status-strip .s-passed, .dot.s-passed, .progress i.s-passed { background: var(--green); }
.status-strip .s-station_done, .dot.s-station_done, .progress i.s-station_done { background: var(--tech-blue); }
.status-strip .s-rework, .dot.s-rework, .progress i.s-rework { background: var(--amber); }
.status-strip .s-failed, .dot.s-failed, .progress i.s-failed { background: var(--red); }
.status-strip .s-packed, .dot.s-packed, .progress i.s-packed { background: #5C6470; }
.status-list { display: grid; gap: 8px; }
.status-row { display: grid; grid-template-columns: 10px 78px 1fr 34px 44px; gap: 8px; align-items: center; font-size: 12px; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.progress { height: 6px; background: var(--bg); border-radius: 4px; overflow: hidden; }
.progress i { display: block; height: 100%; border-radius: 4px; }
.status-row small { color: var(--muted); text-align: right; }
.result-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.result-grid > div { border: 1px solid var(--line); border-radius: 8px; padding: 10px; display: grid; gap: 4px; }
.result-grid span { color: var(--muted); font-size: 11px; }
.result-grid b { font-size: 18px; }
.green { color: var(--green); }
.red { color: var(--red); }
.amber { color: var(--amber); }
.note { color: var(--muted); font-size: 11px; line-height: 1.5; margin-top: 12px; }
.chart-wrap { width: 100%; margin-top: 8px; }
.chart-wrap svg { width: 100%; height: auto; display: block; }
.grid-line { stroke: var(--line); stroke-width: 1; stroke-dasharray: 3 4; }
.axis-label { fill: var(--muted); font-size: 10px; }
.bar { fill: var(--tech-blue); opacity: .75; }
.bar.hot { fill: var(--red); opacity: .82; }
.pareto80-line { stroke: var(--red); stroke-width: 1; stroke-dasharray: 4 4; opacity: .65; }
.pareto-line { fill: none; stroke: var(--tech-blue); stroke-width: 2; }
.pareto-dot { fill: var(--white); stroke: var(--tech-blue); stroke-width: 2; }
.target-line { stroke: var(--red); stroke-width: 1; stroke-dasharray: 5 4; }
.trend-line { fill: none; stroke: var(--tech-blue); stroke-width: 2; }
.trend-dot { fill: var(--tech-blue); }
.trend-dot.empty-dot { fill: var(--white); stroke: var(--muted); }
.bar-list { display: grid; gap: 10px; margin-top: 12px; }
.bar-item { display: grid; grid-template-columns: 24px 1fr; gap: 8px; align-items: center; }
.bar-rank { width: 22px; height: 22px; border-radius: 6px; background: var(--tech-blue-soft); color: var(--tech-blue); display: grid; place-items: center; font-size: 11px; font-weight: 700; }
.bar-copy > div:first-child { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; }
.bar-copy small { color: var(--muted); }
.bar-track { height: 7px; background: var(--bg); border-radius: 4px; margin-top: 4px; overflow: hidden; }
.bar-track i { display: block; height: 100%; background: var(--tech-blue); border-radius: 4px; }
.empty { color: var(--muted); font-size: 12px; padding: 28px 0; text-align: center; }
@media (max-width: 1100px) { .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .split-grid { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .head { flex-direction: column; } .kpi-grid { grid-template-columns: 1fr; } .wip-body { grid-template-columns: 1fr; justify-items: center; } .status-list { width: 100%; } .status-row { grid-template-columns: 10px 68px 1fr 30px 40px; } .result-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
