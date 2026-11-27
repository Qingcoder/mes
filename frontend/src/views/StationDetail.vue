<template>
  <div class="station-detail-page">
    <div class="card">
      <div class="detail-head">
        <div>
          <h2>站点详情</h2>
          <p class="sub">{{ station ? `${station.code} · ${station.name || '未命名站点'}` : '未找到该站点，请返回工艺管理确认站点编码。' }}</p>
        </div>
        <div class="row">
          <router-link class="btn" :to="{ path: '/method', query: { station: station?.code || '' } }">返回工艺管理</router-link>
          <router-link class="btn primary" to="/station">站点作业</router-link>
        </div>
      </div>

      <div v-if="loading" class="msg">正在加载站点详情…</div>
      <div v-else-if="error" class="msg err">{{ error }}</div>

      <template v-else-if="station">
        <div class="kv">
          <div><span>站点编码</span><b class="mono">{{ station.code }}</b></div>
          <div><span>站点名称</span><b>{{ station.name || '—' }}</b></div>
          <div><span>站点类型</span><b>{{ typeLabel(station.type) }}</b></div>
          <div><span>所属分组</span><b>{{ groupName(station.groupId) }}</b></div>
          <div><span>顺序</span><b>{{ station.order || 1 }}</b></div>
          <div><span>状态</span><b>{{ station.enabled === false ? '停用' : '启用' }}</b></div>
          <div><span>工艺参数</span><b>{{ (station.params || []).length }} 个</b></div>
          <div><span>不良代码</span><b>{{ (station.failCodes || []).length }} 个</b></div>
        </div>

        <div v-if="station.description" class="section">
          <h3>站点说明</h3>
          <p class="mini">{{ station.description }}</p>
        </div>

        <div v-if="station.workInstruction" class="section">
          <h3>作业指导</h3>
          <p class="mini">{{ station.workInstruction }}</p>
        </div>

        <div class="section">
          <h3>工艺参数</h3>
          <div v-if="(station.params || []).length" class="table-scroll">
            <table>
              <thead><tr><th>标识</th><th>名称</th><th>值</th><th>单位</th><th>必填</th></tr></thead>
              <tbody>
                <tr v-for="param in station.params || []" :key="param.key">
                  <td class="mono">{{ param.key }}</td>
                  <td>{{ param.label || '—' }}</td>
                  <td>{{ param.value || '—' }}</td>
                  <td>{{ param.unit || '—' }}</td>
                  <td>{{ param.required ? '是' : '否' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty-box">暂无工艺参数</div>
        </div>

        <div class="section">
          <h3>不良代码</h3>
          <div v-if="(station.failCodes || []).length" class="table-scroll">
            <table>
              <thead><tr><th>编码</th><th>名称</th><th>维修手段</th></tr></thead>
              <tbody>
                <tr v-for="code in station.failCodes || []" :key="code.code">
                  <td class="mono">{{ code.code }}</td>
                  <td>{{ code.name || '—' }}</td>
                  <td class="mini">{{ code.repairMethod || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty-box">暂无不良代码</div>
        </div>

        <div class="section">
          <h3>关联对象</h3>
          <div class="relation-grid">
            <div>
              <span>关联产品</span>
              <p class="mini">{{ relationText(station.relatedProducts) }}</p>
            </div>
            <div>
              <span>关联设备</span>
              <p class="mini">{{ relationText(station.relatedEquipment) }}</p>
            </div>
            <div>
              <span>关联人员</span>
              <p class="mini">{{ relationText(station.relatedPersons) }}</p>
            </div>
          </div>
        </div>

        <div v-if="(station.paramFiles || []).length" class="section">
          <h3>参考附件</h3>
          <div class="file-list">
            <div v-for="file in station.paramFiles || []" :key="file.id" class="file-row">
              <span>{{ file.name }}</span>
              <small class="mini">{{ file.extension || '文件' }}</small>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const config = ref<any>(null)
const loading = ref(true)
const error = ref('')

const code = computed(() => String(route.params.code || route.query.station || '').trim().toUpperCase())
const station = computed(() => (config.value?.stations || []).find((s: any) => String(s.code || '').toUpperCase() === code.value) || null)

function typeLabel(value: string) {
  const types = config.value?.options?.stationTypes || []
  return types.find((t: any) => t.value === value)?.label || value || '—'
}
function groupName(groupId: string) {
  const groups = config.value?.groups || []
  return groups.find((g: any) => g.id === groupId)?.name || '—'
}
function relationText(items: any[]) {
  if (!Array.isArray(items) || !items.length) return '未关联'
  return items.map((item: any) => `${item.name || item.code}（${item.code}）`).join('、')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    config.value = await api.processDesign()
    if (!station.value && code.value) error.value = `未找到站点 ${code.value}，请返回工艺管理确认站点编码。`
  } catch (e: any) {
    error.value = e.message || '站点详情加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.station-detail-page { max-width: 980px; margin: 0 auto; }
.detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
.kv { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 24px; padding: 4px 0 16px; }
.kv div { display: flex; flex-direction: column; gap: 4px; }
.kv span { color: var(--muted); font-size: 12px; }
.kv b { font-size: 14px; }
.section { margin-top: 14px; }
.section h3 { margin: 0 0 8px; font-size: 15px; }
.table-scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid var(--line); padding: 8px 10px; text-align: left; }
th { color: var(--muted); }
.empty-box { border: 1px dashed var(--line); border-radius: 6px; padding: 12px; text-align: center; color: var(--muted); font-size: 12px; }
.relation-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.relation-grid > div { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; }
.relation-grid span { display: block; color: var(--muted); font-size: 11px; margin-bottom: 4px; }
.file-list { display: grid; gap: 6px; }
.file-row { display: flex; justify-content: space-between; border: 1px solid var(--line); border-radius: 6px; padding: 7px 10px; font-size: 12px; }
@media (max-width: 768px) { .kv { grid-template-columns: 1fr; } .relation-grid { grid-template-columns: 1fr; } .detail-head { flex-direction: column; } }
</style>
