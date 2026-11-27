<template>
  <div class="role-page">
    <div class="card">
      <div class="role-head">
        <div>
          <h2>角色管理</h2>
          <p class="sub">查看角色与模块权限组合，重新编辑角色名称、描述和权限；角色编码由系统生成，不可修改。</p>
        </div>
        <button class="btn" type="button" @click="openDeleteLog">删除记录</button>
        <router-link class="btn" to="/person">返回人员管理</router-link>
      </div>
      <div class="toolbar">
        <input class="temporarily-hidden" v-model="keyword" placeholder="搜索角色编码 / 名称" @keyup.enter="load" />
        <button class="btn temporarily-hidden" @click="load">查询</button>
        <button class="btn temporarily-hidden" @click="loadAudit">查询日志</button>
      </div>
      <div v-if="msg" class="msg" :class="ok ? 'ok' : 'err'">{{ msg }}</div>

      <p class="table-note">成员只能查看所属地点的工单</p>
      <div class="table-scroll wide">
        <table class="role-table">
          <thead>
            <tr>
              <th>角色</th><th>类型</th><th>权限摘要</th><th>成员与范围</th>
              <th>创建人</th><th>账户类别</th><th>权限</th><th style="text-align:right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, index) in roles" :key="r.code">
              <td>
                <div class="role-cell">
                  <span class="role-avatar" :title="r.name">{{ r.avatar || r.name.slice(0, 1) }}</span>
                  <div class="role-ident">
                    <span class="role-chip" :class="roleTone(r, index)">{{ r.name }}</span>
                    <span class="mono mini">{{ r.code }}</span>
                    <span class="mini role-desc" :title="r.description || ''">{{ r.description || '—' }}</span>
                  </div>
                </div>
              </td>
              <td><span class="tag" :class="r.builtin ? 'station_done' : 'wip'">{{ r.builtin ? '内置' : '自定义' }}</span></td>
              <td>
                <div class="perm-summary">
                  <b>{{ combinationNames(r) || '未配置模块组合' }}</b>
                  <span :title="overviewPermissions(r)">{{ overviewPermissions(r) }}</span>
                </div>
              </td>
              <td>
                <div class="scope-cell">
                  <b>公司成员</b>
                  <span>{{ r.code === 'admin' ? '-' : '戴盟公司' }}</span>
                  <span>全部工单 · 含所有生产地点</span>
                </div>
              </td>
              <td class="mini">{{ r.created_by || '—' }}</td>
              <td>
                <span class="role-chip tone-blue">{{ accountTypeLabel(r) }}</span>
                <div class="mini">{{ (r.accounts || []).length ? `${r.accounts.length} 个已分配账号` : '暂无分配账号' }}</div>
              </td>
              <td>
                <div class="perm-count">
                  <b>{{ r.permissions.length }}</b>
                  <span class="mono">{{ r.perm_mode_code }}</span>
                </div>
              </td>
              <td class="role-actions">
                <button class="btn sm" @click="openView(r)">查看</button>
                <span v-if="r.code === 'admin'" class="mini">超管 · 不可变更</span>
                <template v-else>
                  <button class="btn sm" @click="openEdit(r)">编辑</button>
                  <button class="btn sm" @click="openPerm(r)">权限</button>
                  <button class="btn sm" @click="openRoleAccounts(r)">人员</button>
                  <button v-if="!r.builtin" class="btn sm danger" @click="remove(r)">删除</button>
                </template>
              </td>
            </tr>
            <tr v-if="!roles.length"><td colspan="8" class="empty">暂无角色</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="auditVisible" class="card" style="margin-top:16px">
      <h3>日志查询</h3>
      <p class="sub">复用现有审计日志数据源；仅在显式查询后展示，不自动输出</p>
      <div class="log-tabs">
        <button :class="{ active: logTab === 'permission' }" @click="logTab = 'permission'">权限变更日志</button>
        <button :class="{ active: logTab === 'sn' }" @click="logTab = 'sn'">SN 日志查询</button>
      </div>

      <div v-if="logTab === 'permission'">
        <div class="toolbar">
          <button class="btn sm" @click="loadAudit">刷新日志</button>
          <button class="btn sm" @click="cleanupAudit">清理 90 天前日志</button>
          <button class="btn sm ghost" @click="hideAudit">隐藏日志</button>
        </div>
        <div class="table-scroll medium">
        <table>
          <thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>目标</th><th>详情</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="log in auditLogs" :key="log.id">
              <td class="mini">{{ new Date(log.ts).toLocaleString('zh-CN', { hour12: false }) }}</td>
              <td>{{ log.username }}</td>
              <td class="mono">{{ log.action }}</td>
              <td class="mono">{{ log.target || '—' }}</td>
              <td class="mini">{{ log.detail || '—' }}</td>
              <td>
                <button v-if="log.action === 'role.delete'" class="btn sm" type="button" @click="restoreRole(log.target)">恢复</button>
                <span v-else class="mini">—</span>
              </td>
            </tr>
            <tr v-if="!auditLogs.length"><td colspan="6" class="empty">暂无权限变更日志</td></tr>
          </tbody>
        </table>
        </div>
      </div>

      <div v-else>
        <div class="toolbar">
          <input v-model="snForm.sn" placeholder="输入 SN（精确或模糊）" @keyup.enter="querySn(1)" />
          <select v-model="snForm.match"><option value="exact">精确匹配</option><option value="fuzzy">模糊匹配</option></select>
          <select v-model="snForm.level"><option value="">全部级别</option><option value="INFO">INFO</option><option value="WARN">WARN</option><option value="ERROR">ERROR</option></select>
          <input type="datetime-local" v-model="snForm.fromTs" title="开始时间" />
          <input type="datetime-local" v-model="snForm.toTs" title="结束时间" />
          <select v-model="snForm.sort"><option value="desc">时间倒序</option><option value="asc">时间正序</option></select>
          <button class="btn" :disabled="!snForm.sn || snLoading" @click="querySn(1)">{{ snLoading ? '查询中…' : '查询' }}</button>
          <button class="btn sm ghost" @click="hideAudit">隐藏日志</button>
        </div>
        <div v-if="snError" class="msg err">{{ snError }}</div>
        <div class="table-scroll wide">
        <table>
          <thead><tr><th>时间</th><th>级别</th><th>操作人</th><th>动作</th><th>目标</th><th>详情</th></tr></thead>
          <tbody>
            <tr v-for="log in snRows" :key="log.id">
              <td class="mini">{{ new Date(log.ts).toLocaleString('zh-CN', { hour12: false }) }}</td>
              <td><span class="tag" :class="log.level === 'ERROR' ? 'failed' : (log.level === 'WARN' ? 'repairing' : 'station_done')">{{ log.level }}</span></td>
              <td>{{ log.username }}</td>
              <td class="mono">{{ log.action }}</td>
              <td class="mono">{{ log.target || '—' }}</td>
              <td class="mini">{{ log.detail || '—' }}</td>
            </tr>
            <tr v-if="!snRows.length"><td colspan="6" class="empty">未找到匹配 SN 的日志记录</td></tr>
          </tbody>
        </table>
        </div>
        <div class="pager">
          <button class="btn sm" :disabled="snPage <= 1" @click="querySn(snPage - 1)">上一页</button>
          <span class="mini">第 {{ snPage }} / {{ snPages }} 页 · 共 {{ snTotal }} 条</span>
          <button class="btn sm" :disabled="snPage >= snPages" @click="querySn(snPage + 1)">下一页</button>
        </div>
      </div>
    </div>

    <div v-if="modal === 'view'" class="modal-mask" @click.self="modal = ''">
      <div class="modal wide">
        <h3>查看角色 · {{ current?.name }}（{{ current?.code }}）</h3>
        <div class="kv">
          <div>头像：<b>{{ current?.avatar || current?.name?.slice(0, 1) }}</b></div>
          <div>类型：<b>{{ current?.builtin ? '内置' : '自定义' }}</b></div>
          <div>角色名称：<b>{{ current?.name }}</b></div>
          <div>角色编码：<b class="mono">{{ current?.code }}</b></div>
          <div>账户类别：<b>{{ accountTypeLabel(current) }}</b></div>
          <div>描述：<b>{{ current?.description || '—' }}</b></div>
          <div>已分配人员账号：<b>{{ (current?.accounts || []).join('、') || '—' }}</b></div>
        </div>
        <h4>模块权限组合</h4>
        <div v-if="combinationRows(current).length" class="combo-table">
          <div v-for="m in combinationRows(current)" :key="m.key" class="combo-row">
            <b>{{ m.name }}</b>
            <span class="mono">{{ m.permission }}</span>
            <small class="mono">key={{ m.key }} · order={{ m.order }} · route={{ m.route || '—' }} · component={{ m.component || '—' }} · functionId={{ m.functionId || '—' }}</small>
            <em>{{ m.description }}</em>
            <div v-if="(m.children || []).length" class="combo-children">
              <div v-for="child in m.children" :key="child.id" class="combo-child" :class="{ selected: child.selected }">
                <span>{{ child.selected ? '✓' : '—' }} {{ child.name }}</span>
                <small class="mono">{{ child.permission }} · {{ child.id }}</small>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="mini">该角色未配置模块组合字段，仅显示基础权限。</div>
        <h4>权限项</h4>
        <div v-if="groupedCurrentPerms.length" class="perm-readonly-grouped">
          <div v-for="group in groupedCurrentPerms" :key="group.module" class="perm-readonly-row">
            <b>{{ group.module }}</b>
            <div class="perm-readonly">
              <span v-for="item in group.items" :key="item.code" class="perm-chip" :title="item.code">
                <strong>{{ item.name }}</strong><small class="mono">{{ item.code }}</small>
              </span>
            </div>
          </div>
        </div>
        <div v-else class="perm-readonly">
          <span v-for="p in current?.permissions || []" :key="p" class="perm-chip mono">{{ p }}</span>
          <span v-if="!(current?.permissions || []).length" class="mini">暂无权限</span>
        </div>
        <div class="modal-foot"><button class="btn" @click="modal = ''">关闭</button><button class="btn primary" @click="openEdit(current)">编辑角色</button></div>
      </div>
    </div>

    <div v-if="modal === 'edit'" class="modal-mask" @click.self="modal = ''">
      <div class="modal">
        <h3>编辑角色</h3>
        <div class="field"><label>角色编码（不可编辑）</label><input v-model="form.code" disabled /><div class="mini">角色编码由系统按组合规则生成，修改名称或权限不会影响编码。</div></div>
        <div class="field"><label>角色名称</label><input v-model="form.name" placeholder="如：产线班长" /></div>
        <div class="field">
          <label>账户类别</label>
          <select v-model="form.accountType">
            <option v-for="item in accountTypes" :key="item" :value="item">{{ item }}</option>
          </select>
          <div class="mini">角色本身不创建账号；类别用于标识该角色适用于哪类人员账号。</div>
        </div>
        <div class="field"><label>描述</label><textarea v-model="form.description" placeholder="可选"></textarea></div>
        <div class="modal-foot"><button class="btn" @click="modal = ''">取消</button><button class="btn primary" @click="save">保存</button></div>
      </div>
    </div>

    <div v-if="modal === 'perm'" class="modal-mask" @click.self="modal = ''">
      <div class="modal wide">
        <h3>权限分配 · {{ current?.name }}（{{ current?.code }}）</h3>
        <p class="sub">仅显示当前账号可下放的模块父权限；子权限由各模块内部管理。未勾选的权限将被移除。</p>
        <div v-for="(items, module) in groupedPerms" :key="module" class="perm-group">
          <b>{{ module }}</b>
          <label v-for="p in items" :key="p.code" class="perm-item">
            <input type="checkbox" :value="p.code" v-model="selectedPerms" /> {{ p.name }} <span class="mini mono">{{ p.code }}</span>
          </label>
        </div>
        <div class="modal-foot"><button class="btn" @click="modal = ''">取消</button><button class="btn primary" @click="savePerms">保存权限</button></div>
      </div>
    </div>

    <div v-if="modal === 'roleAccounts'" class="modal-mask" @click.self="modal = ''">
      <div class="modal">
        <h3>已分配人员账号 · {{ roleAccountsFor?.name }}</h3>
        <p class="sub">这些账号属于人员，不属于角色；通过人员管理分配角色后在此反查。角色编码 {{ roleAccountsFor?.code }} · 共 {{ roleAccountRows.length }} 个账号</p>
        <table>
          <thead><tr><th>姓名</th><th>账号</th><th>岗位</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="row in roleAccountRows" :key="row.username">
              <td><button class="link" type="button" @click="showRoleAccount(row)">{{ row.name || row.username }}</button></td>
              <td class="mono">{{ row.username }}</td>
              <td>{{ row.position || '—' }}</td>
              <td>{{ row.status === 'active' ? '启用' : '停用' }}</td>
            </tr>
            <tr v-if="!roleAccountRows.length"><td colspan="4" class="empty">暂无关联账号</td></tr>
          </tbody>
        </table>
        <div class="modal-foot"><button class="btn" type="button" @click="modal = ''">关闭</button></div>
      </div>
    </div>

    <div v-if="userDetail" class="modal-mask" @click.self="userDetail = null">
      <div class="modal">
        <h3>人员详情</h3>
        <div class="kv"><div>姓名：<b>{{ userDetail.name }}</b></div><div>账号：<b class="mono">{{ userDetail.username }}</b></div><div>角色：<b>{{ userDetail.role }}</b></div><div>来源：<b>全局搜索</b></div></div>
        <div class="modal-foot"><button class="btn" @click="userDetail = null">关闭</button></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { routePathByPermission } from '../router/routeConfig'

const route = useRoute()

const roles = ref<any[]>([])
const perms = ref<any[]>([])
const currentPerms = ref<string[]>([])
const keyword = ref('')
const msg = ref('')
const ok = ref(true)
const modal = ref('')
const editing = ref<any>(null)
const current = ref<any>(null)
const form = ref({ code: '', name: '', accountType: '其他', description: '' })
const accountTypes = ['管理员', '生产管理', '工程维护', '现场作业', '访客', '其他']
const selectedPerms = ref<string[]>([])
const auditLogs = ref<any[]>([])
const auditVisible = ref(false)
const userDetail = ref<{ username: string; name: string; role: string } | null>(null)
const roleAccountsFor = ref<any>(null)
const roleAccountRows = ref<any[]>([])

async function loadAudit() {
  auditVisible.value = true
  try { auditLogs.value = await api.permissionAudit(50) }
  catch (e: any) { notify(e.message, false) }
}

function hideAudit() {
  auditVisible.value = false
  auditLogs.value = []
  snRows.value = []; snTotal.value = 0; snPage.value = 1; snError.value = ''
}

async function cleanupAudit() {
  if (!confirm('确认清理 90 天前的权限变更日志？此操作不可恢复。')) return
  try {
    const r = await api.cleanupAudit(90)
    notify(`已清理 ${r.deleted} 条历史日志`); await loadAudit()
  } catch (e: any) { notify(e.message, false) }
}

const logTab = ref<'permission' | 'sn'>('permission')
const snForm = ref({ sn: '', match: 'exact', level: '', fromTs: '', toTs: '', sort: 'desc' })
const snRows = ref<any[]>([])
const snTotal = ref(0)
const snPage = ref(1)
const snPageSize = 20
const snLoading = ref(false)
const snError = ref('')
const snPages = computed(() => Math.max(1, Math.ceil(snTotal.value / snPageSize)))

async function querySn(page = 1) {
  snError.value = ''
  if (!snForm.value.sn.trim()) { snError.value = '请输入 SN'; return }
  snLoading.value = true
  try {
    const r: any = await api.snLogs({
      sn: snForm.value.sn.trim(), match: snForm.value.match, level: snForm.value.level,
      from_ts: snForm.value.fromTs, to_ts: snForm.value.toTs,
      sort: snForm.value.sort, page, page_size: snPageSize,
    })
    snRows.value = r.items || []
    snTotal.value = r.total || 0
    snPage.value = r.page || page
  } catch (e: any) {
    snError.value = e.message; snRows.value = []; snTotal.value = 0
  } finally { snLoading.value = false }
}

const parentPermCodes = computed(() => new Set(
  perms.value.filter((p: any) => p.module === '模块').map((p: any) => p.code),
))
const assignablePerms = computed(() => perms.value.filter(
  (p: any) => parentPermCodes.value.has(p.code) && currentPerms.value.includes(p.code),
))
const groupedPerms = computed(() => {
  const g: Record<string, any[]> = {}
  assignablePerms.value.forEach((p) => { (g[p.module] || (g[p.module] = [])).push(p) })
  return g
})
const groupedCurrentPerms = computed(() => {
  const codes = current.value?.permissions || []
  if (!perms.value.length || !codes.length) return []
  const meta = new Map(perms.value.map((p: any) => [p.code, p]))
  const groups: { module: string; items: { code: string; name: string }[] }[] = []
  codes.forEach((code: string) => {
    const p: any = meta.get(code)
    const rawModule = p?.module || '未登记权限'
    const module = rawModule === '模块' ? '核心模块' : rawModule
    const name = p?.name || code
    let group = groups.find(g => g.module === module)
    if (!group) { group = { module, items: [] }; groups.push(group) }
    group.items.push({ code, name })
  })
  return groups
})

function notify(text: string, good = true) { msg.value = text; ok.value = good }

async function load() {
  try { roles.value = await api.roles(keyword.value) }
  catch (e: any) { notify(e.message, false) }
}

async function openCreate() {
  editing.value = null
  try {
    const r = await api.nextRoleCode()
    form.value = { code: r.code, name: '', accountType: '其他', description: '' }
  } catch (e: any) {
    form.value = { code: '', name: '', accountType: '其他', description: '' }
    notify(e.message, false)
  }
  modal.value = 'edit'
}
function accountTypeLabel(r: any) {
  return r?.accountType || '其他'
}

function combinationRows(r: any) {
  return r?.combination?.modules || []
}
function combinationNames(r: any) {
  return combinationRows(r).map((m: any) => m.name).join('、')
}
function overviewPermissions(r: any) {
  const names = (r.permissions || []).map((code: string) => {
    const hit = perms.value.find((p: any) => p.code === code)
    return hit?.name || code
  })
  return Array.from(new Set(names)).join('、') || combinationNames(r) || r.description || '—'
}
function roleTone(r: any, index: number) {
  if (r.code === 'admin') return 'tone-admin'
  if (r.name?.includes('访客')) return 'tone-guest'
  if (r.name?.includes('主管')) return 'tone-lead'
  if (r.name?.includes('供应链')) return 'tone-supply'
  return ['tone-blue', 'tone-purple', 'tone-green'][index % 3]
}
function openView(r: any) {
  current.value = r
  modal.value = 'view'
}
function openEdit(r: any) {
  editing.value = r
  current.value = r
  form.value = { code: r.code, name: r.name, accountType: r.accountType || '其他', description: r.description || '' }
  modal.value = 'edit'
}

async function save() {
  try {
    const payload = { name: form.value.name, accountType: form.value.accountType, description: form.value.description }
    if (editing.value) await api.updateRole(editing.value.code, payload)
    else await api.createRole(payload)
    modal.value = ''; notify('已保存'); await load()
  } catch (e: any) { notify(e.message, false) }
}

async function openRoleAccounts(r: any) {
  roleAccountsFor.value = r
  roleAccountRows.value = (r.accounts || []).map((username: string) => ({ username }))
  modal.value = 'roleAccounts'
  try {
    const result: any = await api.persons()
    const rows: any[] = result?.items || []
    const byUsername = new Map(rows.map((item: any) => [String(item.username || ''), item]))
    roleAccountRows.value = (r.accounts || []).map((username: string) => {
      const person: any = byUsername.get(username) || {}
      return {
        username,
        name: person.name || username,
        role: person.role || r.code,
        position: person.position || '',
        status: person.status || 'active',
      }
    })
  } catch { /* 人员详情不可用时保留账号名 */ }
}
function showRoleAccount(row: any) {
  userDetail.value = {
    username: row.username,
    name: row.name || row.username,
    role: row.role || roleAccountsFor.value?.code || '',
  }
  modal.value = ''
}
function openDeleteLog() {
  auditVisible.value = true
  logTab.value = 'permission'
  void loadAudit()
}
async function restoreRole(code: string) {
  if (!code || !confirm(`确认恢复角色 ${code}？`)) return
  try {
    await api.restoreRole(code)
    notify('角色已恢复')
    await load(); await loadAudit()
  } catch (e: any) { notify(e.message, false) }
}
async function remove(r: any) {
  if (!confirm(`确认删除角色 ${r.code}？已分配账号会保留，可在“删除记录”中恢复。`)) return
  try {
    await api.deleteRole(r.code)
    notify('已删除，可在“删除记录”中恢复')
    await load()
  } catch (e: any) { notify(e.message, false) }
}

async function openPerm(r: any) {
  current.value = r
  try {
    const allow = new Set(assignablePerms.value.map((p: any) => p.code))
    const held = await api.rolePerms(r.code)
    selectedPerms.value = (held || []).filter((code: string) => allow.has(code))
    modal.value = 'perm'
  } catch (e: any) { notify(e.message, false) }
}

async function savePerms() {
  if (!current.value) return
  try {
    await api.setRolePerms(current.value.code, selectedPerms.value)
    modal.value = ''; notify('权限已保存'); await load()
  } catch (e: any) { notify(e.message, false) }
}

onMounted(async () => {
  try {
    const [permissionRows, me]: any[] = await Promise.all([api.permissions(), api.myPermissions()])
    perms.value = permissionRows
    currentPerms.value = me.permissions || []
    await load()
    if (route.query.user) userDetail.value = {
      username: String(route.query.user),
      name: String(route.query.name || ''),
      role: String(route.query.role || ''),
    }
  } catch (e: any) { notify(e.message, false) }
})
</script>

<style scoped>
.role-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.role-head .btn { flex: none; }
.table-note { margin: 2px 0 10px; padding: 8px 12px; border-radius: 6px; background: #f8fafc; color: var(--muted); font-size: 12px; }
.role-table { width: 100%; border-collapse: separate; border-spacing: 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.role-table th { background: #16243a; color: #fff; border-bottom: 1px solid #16243a; white-space: nowrap; padding: 10px 12px; }
.role-table td { border-bottom: 1px solid var(--line); vertical-align: middle; padding: 12px; }
.role-table tbody tr:last-child td { border-bottom: 0; }
.role-table tbody tr:hover { background: #f8fafc; }
.role-cell { display: flex; align-items: center; gap: 10px; min-width: 250px; }
.role-ident { display: grid; gap: 3px; min-width: 0; }
.role-desc { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.role-chip { display: inline-block; width: fit-content; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.perm-summary { display: grid; gap: 4px; max-width: 360px; min-width: 240px; }
.perm-summary b { color: var(--ink); font-size: 12px; line-height: 1.4; }
.perm-summary span { color: var(--muted); font-size: 11px; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.scope-cell { display: grid; gap: 3px; min-width: 150px; font-size: 12px; }
.scope-cell b { color: var(--ink); }
.scope-cell span { color: var(--muted); font-size: 11px; }
.perm-count { display: grid; gap: 2px; white-space: nowrap; }
.perm-count b { font-size: 14px; }
.perm-count span { color: var(--muted); font-size: 10px; }
.role-actions { white-space: nowrap; }
.tone-admin { color: #d11f3a; background: #fdecef; }
.tone-guest { color: #6b7280; background: #f1f2f4; }
.tone-lead, .tone-supply { color: #6d4aff; background: #f0edff; }
.tone-blue { color: var(--tech-blue); background: var(--tech-blue-soft); }
.tone-purple { color: #7a3db8; background: #f3ebff; }
.tone-green { color: var(--green); background: var(--green-soft); }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap }
.temporarily-hidden { display: none !important; }
.toolbar input { min-width: min(240px, 100%); flex: 1 1 240px; }
.msg { padding: 9px 12px; margin-bottom: 12px; border-radius: 5px }
.msg.ok { background: #e8f4ee; color: #1a7a4c }
.msg.err { background: #fdecea; color: #e61736 }
th, td { font-size: 13px }
.role-avatar { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 7px; background: var(--tech-blue-soft); color: var(--tech-blue); font-weight: 700 }
.modal-mask { position: fixed; inset: 0; background: rgba(20,24,28,.45); display: flex; align-items: center; justify-content: center; z-index: 40 }
.modal { background: #fff; border-radius: 10px; padding: 22px; width: 520px; max-width: 92vw; max-height: min(90dvh, 860px); overflow: auto }
.modal.wide { width: 860px }
.field { margin-bottom: 12px }
.field label { display: block; font-size: 12px; color: #7b828a; margin-bottom: 5px }
.field input, .field textarea { width: 100%; border: 1px solid #d7dbe0; border-radius: 5px; padding: 8px 10px }
.field input:disabled { background: #f4f5f7 }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px }
.perm-group { border: 1px solid #e5e8eb; border-radius: 6px; padding: 12px; margin-bottom: 12px }
.perm-item { display: inline-flex; align-items: center; gap: 6px; margin: 6px 14px 0 0; font-size: 13px }
.inline-check { display: flex; align-items: center; gap: 8px }
.inline-check input[type="checkbox"] { width: auto }
.inline-check label { margin: 0; color: var(--ink); font-weight: 600 }
.account-box { border: 1px solid var(--line); border-radius: 6px; padding: 12px; margin-bottom: 12px; background: #fafbfc }
.log-tabs { display: flex; gap: 6px; border-bottom: 1px solid #e5e8eb; margin-bottom: 12px }
.log-tabs button { border: 0; background: transparent; padding: 8px 14px; cursor: pointer; color: #666 }
.log-tabs button.active { color: #e61736; border-bottom: 2px solid #e61736; font-weight: 600 }
.kv { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px 18px; font-size: 13px; margin-bottom: 14px }
.kv > div { padding: 6px 0; border-bottom: 1px solid var(--line) }
.modal h4 { font-size: 14px; margin: 14px 0 8px }
.combo-table { border: 1px solid var(--line); border-radius: 6px; overflow: hidden }
.combo-row { display: grid; gap: 3px; padding: 8px 10px; border-bottom: 1px solid var(--line); font-size: 12px }
.combo-row:last-child { border-bottom: 0 }
.combo-row small { color: var(--muted); word-break: break-all }
.combo-row em { color: var(--muted); font-style: normal }
.combo-children { margin-top: 6px; border-top: 1px dashed var(--line); padding-top: 5px; }
.combo-child { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; color: var(--muted); padding: 3px 0; }
.combo-child.selected { color: var(--tech-blue); font-weight: 600; }
.combo-child small { font-size: 10px; }
.perm-readonly { display: flex; flex-wrap: wrap; gap: 6px }
.perm-readonly-grouped { display: grid; gap: 9px }
.perm-readonly-row { display: grid; grid-template-columns: 84px minmax(0, 1fr); gap: 8px; align-items: start; }
.perm-readonly-row > b { color: var(--muted); font-size: 12px; padding-top: 6px; }
.perm-chip { display: inline-flex; flex-direction: column; gap: 2px; padding: 5px 8px; border-radius: 4px; background: var(--tech-blue-soft); color: var(--tech-blue); font-size: 11px; }
.perm-chip strong { font-weight: 700; }
.perm-chip small { color: var(--muted); font-size: 10px; }
.pager { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 12px; flex-wrap: wrap }
@media (max-width: 768px) { .kv { grid-template-columns: 1fr; } .perm-readonly-row { grid-template-columns: 1fr; } .perm-readonly-row > b { padding-top: 0; } .role-cell, .perm-summary, .scope-cell { min-width: 0; } .role-desc { max-width: 160px; } }
@media (max-width: 480px) { .toolbar input[type="datetime-local"] { min-width: 100%; } }
.toolbar input[type="datetime-local"] { min-width: 190px }
</style>
