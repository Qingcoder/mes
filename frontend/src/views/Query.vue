<template>
  <div>
    <div class="grid g3">
      <div class="card">
        <h2>按 SN 追溯</h2>
        <div class="field"><label>SN</label><input v-model="sn" class="mono" placeholder="DAP93226AS00019D" /></div>
        <button class="btn primary" @click="doSN">查询</button>
      </div>
      <div class="card">
        <h2>按工单查进度</h2>
        <div class="field"><label>工单</label><select v-model="woId"><option value="">请选择</option><option v-for="w in wos" :key="w.id" :value="w.id">{{ w.wo_no }}</option></select></div>
        <button class="btn primary" @click="doWO" :disabled="!woId">查询</button>
      </div>
      <div class="card">
        <h2>按箱号查</h2>
        <div class="field"><label>箱号</label><input v-model="boxNo" class="mono" placeholder="BOX-001" /></div>
        <button class="btn primary" @click="doBox">查询</button>
      </div>
    </div>
    <div v-if="err" class="msg err">{{ err }}</div>

    <div v-if="snResult" class="card">
      <h2>SN 追溯结果 · <span class="mono">{{ snResult.unit.sn }}</span></h2>
      <p class="sub">工单 {{ snResult.wo_no }} · 当前状态 <span :class="['tag', snResult.unit.state]">{{ snResult.unit.state }}</span> · 箱号 {{ snResult.unit.box_no || '—' }}</p>
      <div v-if="(snResult.chain || []).length > 1" class="chain-block">
        <b>SN 替换链</b>
        <div class="chain-line">
          <template v-for="(item, index) in snResult.chain" :key="item.sn + index">
            <span class="chain-node" :class="item.role">{{ item.sn }}</span>
            <span v-if="index < snResult.chain.length - 1" class="chain-arrow">→</span>
          </template>
        </div>
        <p class="mini">共 {{ snResult.chain.length - 1 }} 次替换，当前 SN {{ snResult.unit.sn }}</p>
      </div>
      <div class="table-scroll">
      <table><thead><tr><th>站点</th><th>结果</th><th>不良码</th><th>操作人</th><th>时间</th></tr></thead>
        <tbody><tr v-for="r in snResult.records" :key="r.id"><td>{{ r.station }}</td><td><span :class="['tag', r.result === 'pass' ? 'station_done' : 'failed']">{{ r.result }}</span></td><td>{{ r.fail_code || '—' }}</td><td>{{ r.operator || '—' }}</td><td class="mono">{{ fmt(r.created_at) }}</td></tr></tbody>
      </table>
      </div>
    </div>

    <div v-if="woResult" class="card">
      <h2>工单进度 · {{ woResult.wo.wo_no }}</h2>
      <div class="grid g3">
        <div><label>总数</label><div style="font-size:30px;font-weight:800">{{ woResult.total }}</div></div>
        <div><label>已过站</label><div style="font-size:30px;font-weight:800;color:var(--green)">{{ woResult.station_done }}</div></div>
        <div><label>已装箱</label><div style="font-size:30px;font-weight:800;color:var(--red)">{{ woResult.packed }}</div></div>
      </div>
    </div>

    <div v-if="boxResult" class="card">
      <h2>箱号 · <span class="mono">{{ boxResult.box.box_no }}</span></h2>
      <p class="sub">工单 {{ boxResult.wo_no }} · {{ boxResult.box.qty }} 台 · 封箱 {{ fmt(boxResult.box.closed_at) }}</p>
      <div class="mono" style="line-height:1.9">{{ boxResult.sns.join('\n') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const wos = ref<any[]>([])
const sn = ref(''); const woId = ref<number | ''>(''); const boxNo = ref('')
const snResult = ref<any>(null); const woResult = ref<any>(null); const boxResult = ref<any>(null)
const err = ref('')
onMounted(async () => {
  wos.value = await api.listWO()
  if (route.query.sn) { sn.value = String(route.query.sn); doSN() }
  if (route.query.wo) { woId.value = Number(route.query.wo); doWO() }
  if (route.query.box) { boxNo.value = String(route.query.box); doBox() }
})
function fmt(t: string) { return t ? new Date(t).toLocaleString('zh-CN') : '—' }
async function run(fn: () => Promise<any>, set: (v: any) => void) {
  err.value = ''; try { set(await fn()) } catch (e: any) { err.value = e.message }
}
const doSN = () => run(() => api.querySN(sn.value.trim()), v => { snResult.value = v; woResult.value = boxResult.value = null })
const doWO = () => run(() => api.queryWO(Number(woId.value)), v => { woResult.value = v; snResult.value = boxResult.value = null })
const doBox = () => run(() => api.queryBox(boxNo.value.trim()), v => { boxResult.value = v; snResult.value = woResult.value = null })
</script>

<style scoped>
.chain-block { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; margin: 10px 0 14px; }
.chain-line { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
.chain-node { padding: 3px 8px; border-radius: 4px; background: #f4f6fa; font-family: ui-monospace, monospace; font-size: 12px; }
.chain-node.origin { background: #eef1f6; color: var(--muted); }
.chain-node.replaced { background: var(--red-soft); color: var(--red); text-decoration: line-through; }
.chain-node.current { background: var(--green-soft); color: var(--green); font-weight: 700; }
.chain-arrow { color: var(--muted); font-size: 12px; }
</style>
