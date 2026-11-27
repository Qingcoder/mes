<template>
  <div class="detail-wrap">
    <div class="card detail-card">
      <div class="detail-head">
        <div>
          <h2>SN 详情</h2>
          <p class="sub">当前 SN 的工单、状态与逐站过站记录</p>
        </div>
        <button class="btn" @click="router.push('/station')">返回过站</button>
      </div>

      <div v-if="!sn" class="msg err">未获取到 SN，请从过站页点击详情。</div>

      <template v-else>
        <div v-if="loading" class="msg">加载中…</div>
        <div v-else-if="error" class="msg err">{{ error }}</div>
        <template v-else-if="detail">
          <div class="kv">
            <div><span>SN</span><b class="mono">{{ detail.unit.sn }}</b></div>
            <div><span>工单</span><b class="mono">{{ detail.wo_no || '—' }}</b></div>
            <div><span>当前状态</span><b><span class="tag" :class="detail.unit.state">{{ detail.unit.state }}</span></b></div>
            <div><span>当前站点</span><b>{{ detail.unit.current_station || '—' }}</b></div>
            <div><span>不良代码</span><b class="mono">{{ detail.unit.fail_code || '—' }}</b></div>
            <div><span>箱号</span><b class="mono">{{ detail.unit.box_no || '—' }}</b></div>
          </div>

          <div v-if="(detail.chain || []).length > 1" class="chain-block">
            <h3>SN 替换链</h3>
            <p class="sub">同一台设备多次换标：{{ detail.chain.length - 1 }} 次替换，查询任一 SN 都能定位到当前设备。</p>
            <div class="table-scroll">
              <table>
                <thead><tr><th>顺序</th><th>SN</th><th>状态</th><th>站点</th><th>操作人</th><th>原因</th><th>时间</th></tr></thead>
                <tbody>
                  <tr v-for="(item, index) in detail.chain" :key="item.sn + index">
                    <td>{{ index + 1 }}</td>
                    <td class="mono">{{ item.sn }}</td>
                    <td><span class="tag" :class="item.role === 'current' ? 'station_done' : 'failed'">{{ item.role === 'origin' ? '原始' : item.role === 'current' ? '当前' : '已替换' }}</span></td>
                    <td>{{ item.station || '—' }}</td>
                    <td>{{ item.operator || '—' }}</td>
                    <td class="mini">{{ item.reason || '—' }}</td>
                    <td class="mono mini">{{ fmt(item.createdAt) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <h3>过站记录</h3>
          <div class="table-scroll">
            <table>
              <thead><tr><th>站点</th><th>结果</th><th>不良代码</th><th>操作人</th><th>时间</th></tr></thead>
              <tbody>
                <tr v-for="r in detail.records || []" :key="r.id">
                  <td>{{ r.station }}</td>
                  <td><span class="tag" :class="r.result === 'pass' ? 'station_done' : 'failed'">{{ r.result }}</span></td>
                  <td class="mono">{{ r.fail_code || '—' }}</td>
                  <td>{{ r.operator || '—' }}</td>
                  <td class="mono">{{ fmt(r.created_at) }}</td>
                </tr>
                <tr v-if="!(detail.records || []).length"><td colspan="5" class="empty">暂无过站记录</td></tr>
              </tbody>
            </table>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const router = useRouter()
const sn = ref(String(route.query.sn || localStorage.getItem('mes_last_sn') || ''))
const detail = ref<any>(null)
const loading = ref(false)
const error = ref('')

function fmt(t: string) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '—'
}

async function load() {
  if (!sn.value) return
  loading.value = true; error.value = ''; detail.value = null
  try { detail.value = await api.unifiedQuerySn(sn.value) }
  catch (e: any) { error.value = e.message || '详情加载失败' }
  finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.detail-wrap { max-width: 980px; margin: 0 auto; }
.detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.kv { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 24px; padding: 12px 0 20px; }
.kv div { display: flex; flex-direction: column; gap: 4px; }
.kv span { color: var(--muted); font-size: 12px; }
.kv b { color: var(--ink); font-size: 15px; }
h3 { margin: 8px 0 12px; }
.chain-block { margin: 10px 0 18px; }
.chain-block .sub { margin: 0 0 8px; }
@media (max-width: 768px) { .kv { grid-template-columns: 1fr; } }
</style>
