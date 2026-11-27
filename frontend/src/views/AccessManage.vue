<template>
  <div class="access-wrap">
    <div class="card">
      <div class="head">
        <div>
          <h2>站点与流程权限</h2>
          <p class="sub">按站点或流程维度授权给角色/用户；用户级授权优先，拒绝优先。</p>
        </div>
        <div class="row">
          <button class="btn" @click="router.push('/station')">返回过站</button>
          <button v-if="canManage" class="btn primary" @click="openCreate">新增授权</button>
        </div>
      </div>

      <div v-if="!canManage" class="msg err">当前账号无站点流程权限管理权限。</div>
      <template v-else>
        <div v-if="error" class="msg err">{{ error }}</div>

        <div class="filters">
          <select v-model="filter.scopeType">
            <option value="">全部维度</option>
            <option value="station">站点</option>
            <option value="flow">流程</option>
          </select>
          <select v-model="filter.targetType">
            <option value="">全部对象</option>
            <option value="role">角色</option>
            <option value="user">用户</option>
          </select>
          <input v-model="filter.keyword" placeholder="搜索站点 / 流程 / 对象" />
        </div>

        <div class="table-scroll wide">
          <table>
            <thead>
              <tr>
                <th>授权编号</th><th>维度</th><th>授权值</th><th>对象类型</th><th>被授权对象</th>
                <th>效果</th><th>操作</th><th>说明</th><th>更新人 / 时间</th><th style="text-align:right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="g in filteredGrants" :key="g.grantId">
                <td class="mono">{{ g.grantId }}</td>
                <td>{{ scopeLabel(g.scopeType) }}</td>
                <td class="mono">{{ g.scopeValue }}</td>
                <td>{{ g.targetType === 'role' ? '角色' : '用户' }}</td>
                <td>{{ targetLabel(g.targetType, g.targetValue) }}</td>
                <td><span class="tag" :class="g.effect === 'deny' ? 'failed' : 'station_done'">{{ effectLabel(g.effect) }}</span></td>
                <td>{{ actionLabels(g.actions) }}</td>
                <td class="mini">{{ g.description || '—' }}</td>
                <td class="mini">{{ g.updatedBy || '—' }} / {{ fmt(g.updatedAt) }}</td>
                <td style="text-align:right">
                  <button class="btn sm" @click="openView(g)">查看</button>
                  <button class="btn sm" @click="openEdit(g)">编辑</button>
                  <button class="btn sm danger" @click="remove(g)">删除</button>
                </td>
              </tr>
              <tr v-if="!filteredGrants.length"><td colspan="10" class="empty">暂无授权配置</td></tr>
            </tbody>
          </table>
        </div>

        <p class="mini relation">关系说明：账号 → 角色 → 功能权限；站点/流程授权可绑定角色或用户，用户级优先于角色级，拒绝优先于允许。保存后立即生效，无需重启。</p>
      </template>
    </div>

    <div v-if="modal" class="modal-mask" @click.self="modal = ''">
      <div class="modal">
        <h3>{{ modal === 'create' ? '新增授权' : modal === 'edit' ? '编辑授权' : '查看授权' }}</h3>
        <template v-if="modal !== 'delete'">
          <div class="field"><label>授权维度</label>
            <select v-model="form.scopeType" :disabled="readonly">
              <option value="station">站点</option><option value="flow">流程</option>
            </select>
          </div>
          <div class="field"><label>授权值</label>
            <input v-if="form.scopeType === 'station'" v-model="form.scopeValue" list="station-options" placeholder="如 OP10" :disabled="readonly" />
            <input v-else v-model="form.scopeValue" list="flow-options" placeholder="如 OP10>OP20" :disabled="readonly" />
            <datalist id="station-options"><option v-for="s in options.stations" :key="s" :value="s" /></datalist>
            <datalist id="flow-options"><option v-for="f in options.flows" :key="f" :value="f" /></datalist>
          </div>
          <div class="field"><label>对象类型</label>
            <select v-model="form.targetType" :disabled="readonly">
              <option value="role">角色</option><option value="user">用户</option>
            </select>
          </div>
          <div class="field"><label>被授权对象</label>
            <select v-if="form.targetType === 'role'" v-model="form.targetValue" :disabled="readonly">
              <option value="">请选择角色</option>
              <option v-for="r in options.roles" :key="r.value" :value="r.value">{{ r.label }}（{{ r.value }}）</option>
            </select>
            <select v-else v-model="form.targetValue" :disabled="readonly">
              <option value="">请选择用户</option>
              <option v-for="u in options.users" :key="u.value" :value="u.value">{{ u.label }}（{{ u.value }}）</option>
            </select>
          </div>
          <div class="field"><label>效果</label>
            <select v-model="form.effect" :disabled="readonly">
              <option value="allow">允许</option><option value="deny">拒绝</option>
            </select>
          </div>
          <div class="field"><label>操作</label>
            <div class="checks">
              <label><input type="checkbox" value="view" v-model="form.actions" :disabled="readonly" /> 查看</label>
              <label><input type="checkbox" value="operate" v-model="form.actions" :disabled="readonly" /> 操作</label>
            </div>
          </div>
          <div class="field"><label>说明</label><textarea v-model="form.description" rows="3" :disabled="readonly" /></div>
        </template>
        <div v-else class="msg err">确认删除该授权？删除后记录会保留在审计日志中。</div>
        <div class="modal-foot">
          <button class="btn" @click="modal = ''">{{ readonly ? '关闭' : '取消' }}</button>
          <button v-if="!readonly" class="btn primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { sharedPerms } from '../stores/permStore'

const router = useRouter()
const canManage = computed(() => sharedPerms.value.includes('system:access:manage') || sharedPerms.value.includes('system:role:manage'))
const grants = ref<any[]>([])
const options = ref<any>({ stations: [], flows: [], roles: [], users: [] })
const filter = ref({ scopeType: '', targetType: '', keyword: '' })
const error = ref('')
const saving = ref(false)
const modal = ref('')
const readonly = ref(false)
const editingId = ref('')
const form = ref<any>(blank())

function blank() {
  return { scopeType: 'station', scopeValue: '', targetType: 'role', targetValue: '', effect: 'allow', actions: ['view', 'operate'], description: '' }
}
function fmt(v?: string) { return v ? new Date(v).toLocaleString('zh-CN', { hour12: false }) : '—' }
function scopeLabel(v: string) { return v === 'flow' ? '流程' : '站点' }
function effectLabel(v: string) { return v === 'deny' ? '拒绝' : '允许' }
function actionLabels(actions: string[]) { return (actions || []).map(a => a === 'view' ? '查看' : '操作').join('、') || '—' }
function targetLabel(type: string, value: string) {
  const arr = type === 'role' ? options.value.roles : options.value.users
  return arr.find((x: any) => x.value === value)?.label || value
}

const filteredGrants = computed(() => {
  const f = filter.value
  return grants.value.filter(g => {
    if (f.scopeType && g.scopeType !== f.scopeType) return false
    if (f.targetType && g.targetType !== f.targetType) return false
    if (!f.keyword) return true
    const text = `${g.scopeValue} ${g.targetValue} ${g.description || ''}`.toLowerCase()
    return text.includes(f.keyword.toLowerCase())
  })
})

async function load() {
  error.value = ''
  try {
    options.value = await api.accessOptions()
    grants.value = (await api.accessGrants()).items || []
  } catch (e: any) { error.value = e.message || '加载失败' }
}
function openCreate() { editingId.value = ''; readonly.value = false; modal.value = 'create'; form.value = blank() }
function openView(g: any) { editingId.value = g.grantId; readonly.value = true; modal.value = 'view'; form.value = { ...g, actions: [...(g.actions || [])] } }
function openEdit(g: any) { editingId.value = g.grantId; readonly.value = false; modal.value = 'edit'; form.value = { ...g, actions: [...(g.actions || [])] } }
async function remove(g: any) {
  if (!confirm(`确认删除授权 ${g.grantId}？`)) return
  try { await api.deleteAccessGrant(g.grantId); modal.value = ''; await load() }
  catch (e: any) { error.value = e.message }
}
async function save() {
  saving.value = true; error.value = ''
  try {
    const payload = {
      scopeType: form.value.scopeType, scopeValue: form.value.scopeValue.trim(),
      targetType: form.value.targetType, targetValue: form.value.targetValue,
      effect: form.value.effect, actions: form.value.actions,
      description: form.value.description || '', enabled: true,
    }
    if (modal.value === 'edit') await api.updateAccessGrant(editingId.value, payload)
    else await api.createAccessGrant(payload)
    modal.value = ''; await load()
  } catch (e: any) { error.value = e.message }
  finally { saving.value = false }
}

onMounted(() => { if (canManage.value) void load() })
</script>

<style scoped>
.access-wrap { max-width: 1180px; margin: 0 auto; }
.head { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.filters { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.filters select, .filters input { width: auto; min-width: 180px; }
.checks { display: flex; gap: 18px; }
.checks label { display: inline-flex; align-items: center; gap: 6px; }
.checks input { width: auto; }
.relation { margin-top: 14px; line-height: 1.7; }
.modal-mask { position: fixed; inset: 0; background: rgba(4,8,18,.6); display: grid; place-items: center; z-index: 80; padding: 16px; }
.modal { width: 100%; max-width: 520px; max-height: 90vh; overflow: auto; background: var(--white); border-radius: 10px; padding: 20px; }
.modal h3 { margin-bottom: 16px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
</style>
