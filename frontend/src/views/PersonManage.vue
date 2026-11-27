<template>
  <div class="person-page">
    <div class="head">
      <div>
        <h2>人员管理</h2>
        <p class="sub">维护员工档案、岗位归属与系统账号，按岗位角色配置工单管理、生产报工、物料追溯、设备状态、质量检验等模块的访问权限；人员主数据可供各生产模块调用。</p>
      </div>
      <div class="row">
        <router-link v-if="canCreateRole" class="btn" to="/roles">角色管理</router-link>
        <button v-if="canManage" class="btn primary" type="button" @click="openCreate">新增人员</button>
      </div>
    </div>

    <FixedModuleNotice module-key="person" />

    <div v-if="!canView" class="msg err">当前账号无人员模块访问权限。</div>
    <template v-else>
      <div v-if="!canManage" class="msg">当前账号仅可查看人员档案，新增、编辑、分配角色与权限需要用户管理或角色权限管理权限。</div>
      <div v-if="error" class="msg err">{{ error }}</div>
      <div v-if="loading" class="msg">加载人员档案…</div>

      <div class="person-layout">
        <aside class="tree-panel">
          <div class="panel-title">岗位树</div>
          <PersonOrgTree
            :persons="persons"
            :selected="treeSelected"
            :can-edit="canManage"
            @select="selectTree"
            @edit="openPositionEdit"
          />
        </aside>

        <main class="list-panel">
          <div class="toolbar">
            <input v-model="keyword" placeholder="搜索姓名 / 账号 / 岗位" />
            <input v-model="parentKeyword" placeholder="按上级 / 挂靠人查询" @keyup.enter="reload" />
            <button class="btn" type="button" @click="reload">刷新</button>
          </div>

          <div class="table-scroll medium">
          <table>
            <thead>
              <tr><th>人员</th><th>角色</th><th>岗位</th><th>上级 / 挂靠</th><th>状态</th><th>权限</th><th style="text-align:right">操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="p in filteredPersons" :key="p.username" :title="canManage ? '双击修改权限' : ''" @dblclick="canManage && openAccess(p)">
                <td><b>{{ p.name || p.username }}</b><div class="mini mono">{{ p.username }}</div></td>
                <td>{{ roleName(p.role) }}</td>
                <td>{{ p.position || '—' }}</td>
                <td>{{ parentLabel(p.parentUsername) }}</td>
                <td><span class="tag" :class="p.status === 'active' ? 'station_done' : 'failed'">{{ p.status === 'active' ? '启用' : '停用' }}</span></td>
                <td>
                  <button v-if="canManage" class="link" type="button" @click.stop="openAccess(p)">编辑权限</button>
                  <span v-else class="mini">{{ (p.permissions || []).length }} 项</span>
                </td>
                <td style="text-align:right" @dblclick.stop>
                  <button class="btn sm" type="button" @click="openScope(p)">详情</button>
                  <button v-if="canManage" class="btn sm" type="button" @click="openLink(p)">挂靠</button>
                  <button v-if="canManage && p.parentUsername" class="btn sm" type="button" @click="unlink(p)">取消挂靠</button>
                  <button v-if="canManage" class="btn sm" type="button" @click="openRole(p)">改角色</button>
                  <button v-if="canManage" class="btn sm" type="button" @click="openEdit(p)">编辑</button>
                  <button v-if="canManage" class="btn sm" type="button" @click="openAccess(p)">权限</button>
                </td>
              </tr>
              <tr v-if="!filteredPersons.length"><td colspan="7" class="empty">暂无人员记录</td></tr>
            </tbody>
          </table>
          </div>
        </main>
      </div>
    </template>

    <div v-if="linkOpen" class="modal-mask" @click.self="linkOpen = false">
      <div class="modal link-modal" role="dialog" aria-modal="true">
        <h3>设置挂靠关系</h3>
        <div class="field"><label>人员</label><b>{{ linkPerson?.name || linkPerson?.username }}（{{ linkPerson?.username }}）</b></div>
        <div class="field">
          <label>上级 / 挂靠人</label>
          <select v-model="linkParent">
            <option value="">不挂靠</option>
            <option v-for="p in linkOptions" :key="p.username" :value="p.username">{{ p.name }}（{{ p.username }}）</option>
          </select>
        </div>
        <p class="hint">选择“不挂靠”可解除当前关系；保存后列表和岗位树数据会同步刷新。</p>
        <div v-if="linkError" class="msg err">{{ linkError }}</div>
        <div class="modal-foot">
          <button class="btn" type="button" @click="linkOpen = false">取消</button>
          <button class="btn primary" type="button" :disabled="linkSaving" @click="saveLink">{{ linkSaving ? '保存中…' : '保存挂靠' }}</button>
        </div>
      </div>
    </div>

    <div v-if="positionEditOpen" class="modal-mask" @click.self="positionEditOpen = false">
      <div class="modal position-modal" role="dialog" aria-modal="true">
        <h3>编辑岗位</h3>
        <div v-if="positionError" class="msg err">{{ positionError }}</div>
        <div class="field"><label>原岗位</label><input :value="positionFrom" disabled /></div>
        <div class="field"><label>新岗位</label><input v-model="positionTo" autofocus @keyup.enter="savePosition" /></div>
        <p class="hint">保存后会更新该岗位下所有人员，角色和权限不变。</p>
        <div class="modal-foot">
          <button class="btn" type="button" @click="positionEditOpen = false">取消</button>
          <button class="btn primary" type="button" :disabled="positionSaving" @click="savePosition">{{ positionSaving ? '保存中…' : '保存岗位' }}</button>
        </div>
      </div>
    </div>

    <div v-if="modal" class="modal-mask" @click.self="modal = ''">
      <div class="modal">
        <h3>{{ modalTitle }}</h3>

        <template v-if="modal === 'create' || modal === 'edit'">
          <div class="grid2">
            <div class="field"><label>姓名</label><input v-model="form.name" /></div>
            <div class="field">
              <label>登录用户名</label>
              <input
                id="person-username"
                v-model="form.username"
                name="person_new_username"
                autocomplete="off"
                autocapitalize="none"
                spellcheck="false"
                placeholder="请自行输入登录用户名"
                :disabled="modal === 'edit'"
              />
            </div>
          </div>
          <div class="grid2">
            <div class="field">
              <label>角色</label>
              <button class="role-select" type="button" :disabled="modal === 'edit'" @click="openRoleWindow">
                <span>{{ selectedRoleLabel }}</span><span aria-hidden="true">▾</span>
              </button>
              <span v-if="roleNotice" class="role-notice">{{ roleNotice }}</span>
            </div>
            <div class="field">
              <label>{{ modal === 'create' ? '初始密码' : '密码' }}</label>
              <input
                id="person-password"
                v-model="form.password"
                name="person_new_password"
                type="password"
                autocomplete="new-password"
                :placeholder="modal === 'create' ? '请自行输入初始密码，至少 6 位' : '留空不修改；填写则重置密码'"
              />
            </div>
          </div>
          <div class="account-clear-row">
            <button class="link" type="button" @click="clearAccountFields">清空账号与密码</button>
            <span>账号与密码仅由当前填写人输入，不提供默认值。</span>
          </div>
          <div class="grid2">
            <div class="field"><label>岗位</label><input v-model="form.position" /></div>
            <div class="field">
              <label>上级 / 挂靠人</label>
              <select v-model="form.parentUsername">
                <option value="">不挂靠</option>
                <option v-for="p in parentOptions" :key="p.username" :value="p.username">{{ p.name }}（{{ p.username }}）</option>
              </select>
            </div>
          </div>
          <div class="grid2">
            <div class="field"><label>状态</label><select v-model="form.status"><option value="active">启用</option><option value="disabled">停用</option></select></div>
          </div>
          <div class="relation-block">
            <div class="section-head"><b>关联对象</b><span class="mini">与其他模块自动同步</span></div>
            <div class="relation-grid">
              <label>关联站点<select v-model="form.relatedStations" multiple><option v-for="item in relationOptions.stations" :key="'s-' + item.code" :value="item.code">{{ item.code }} · {{ item.name }}</option></select></label>
              <label>关联产品<select v-model="form.relatedProducts" multiple><option v-for="item in relationOptions.products" :key="'p-' + item.code" :value="item.code">{{ item.code }} · {{ item.name }}</option></select></label>
              <label>关联设备<select v-model="form.relatedEquipment" multiple><option v-for="item in relationOptions.equipment" :key="'e-' + item.code" :value="item.code">{{ item.code }} · {{ item.name }}</option></select></label>
            </div>
          </div>
          <div class="field"><label>备注</label><textarea v-model="form.notes" rows="2" /></div>
          <div class="field"><label>按角色权限展示的路由入口</label><ModuleAccessTree :permissions="rolePermissions" /></div>
          <div v-if="formError" class="msg err">{{ formError }}</div>
          <div class="modal-foot"><button class="btn" type="button" @click="modal = ''">取消</button><button class="btn primary" type="button" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button></div>
        </template>

        <template v-else-if="modal === 'access'">
          <div class="field"><label>人员</label><b>{{ accessPerson?.name }}（{{ accessPerson?.username }}）</b></div>
          <div class="field"><label>角色</label><b>{{ roleName(accessPerson?.role) }}</b></div>
          <p class="hint">勾选可访问的模块，再点“详情权限”编辑子权限；保存后按人员权限覆盖角色默认权限。只能勾选当前账号已有的权限。</p>
          <div class="module-perm-grid">
            <div v-for="item in assignableModulePerms" :key="item.code" class="module-perm-item">
              <label class="module-perm-main">
                <input v-model="accessPermissions" type="checkbox" :value="item.code" />
                <span><b>{{ item.name }}</b><small class="mono">{{ item.path }}</small></span>
              </label>
              <button class="link" type="button" @click="openPermissionDetail(item)">详情权限</button>
            </div>
          </div>
          <div v-if="!assignableModulePerms.length" class="msg err">当前账号没有可下放的模块权限。</div>
          <div v-if="permissionError" class="msg err">{{ permissionError }}</div>
          <div class="modal-foot">
            <button class="btn" type="button" @click="modal = ''">取消</button>
            <button class="btn primary" type="button" :disabled="permissionSaving" @click="saveAccessPermissions">{{ permissionSaving ? '保存中…' : '保存权限' }}</button>
          </div>
        </template>
      </div>
    </div>

    <div v-if="detailOpen" class="modal-mask detail-mask" @click.self="detailOpen = false">
      <div class="modal detail-modal" role="dialog" aria-modal="true">
        <h3>{{ detailModule?.name || '模块' }} · 子权限详情</h3>
        <p class="hint">只显示当前账号已持有、且属于该模块的子权限。勾选后点确定，再在人员权限弹窗保存。</p>
        <div class="detail-perm-grid">
          <label v-for="item in detailPermOptions" :key="item.code" class="detail-perm-item">
            <input v-model="detailSelected" type="checkbox" :value="item.code" />
            <span><b>{{ item.name }}</b><small class="mono">{{ item.code }}</small></span>
          </label>
        </div>
        <div v-if="!detailPermOptions.length" class="msg err">当前账号没有可下放的该模块子权限。</div>
        <div class="modal-foot">
          <button class="btn" type="button" @click="detailOpen = false">取消</button>
          <button class="btn primary" type="button" @click="savePermissionDetail">确定</button>
        </div>
      </div>
    </div>

    <div v-if="roleWindowOpen" class="role-window-mask" @click.self="closeRoleWindow">
      <div class="role-window" role="dialog" aria-modal="true" aria-labelledby="role-window-title">
        <div class="role-window-head">
          <h3 id="role-window-title">角色与权限模块</h3>
          <button class="btn sm" type="button" @click="closeRoleWindow">关闭</button>
        </div>
        <p class="hint">选择已有角色，或按模块权限组合创建新角色；生成后自动保存为默认值并选中。</p>
        <div class="field">
          <label>已有角色</label>
          <select v-model="selectedExistingRole" @change="chooseExistingRole">
            <option value="">请选择已有角色</option>
            <option v-for="r in roles" :key="r.code" :value="r.code">{{ r.name }}（{{ r.code }}）</option>
          </select>
        </div>
        <div v-if="canCreateRole" class="combo-section">
          <div class="combo-title">按模块权限组合生成新角色</div>
          <RoleCombinationForm compact @created="onComboRoleCreated" />
        </div>
      </div>
    </div>

    <div v-if="scopeOpen" class="modal-mask" @click.self="scopeOpen = false">
      <div class="modal detail-modal" role="dialog" aria-modal="true">
        <h3>人员详情与统筹范围</h3>
        <div v-if="scopeError" class="msg err">{{ scopeError }}</div>
        <div v-if="scopeData" class="info-grid">
          <div><label>姓名</label><b>{{ scopeData.name || scopeData.username }}</b></div>
          <div><label>登录账号</label><b class="mono">{{ scopeData.username }}</b></div>
          <div><label>角色</label><b>{{ roleName(scopeData.role) }}</b></div>
          <div><label>岗位</label><b>{{ scopeData.position || '—' }}</b></div>
          <div><label>部门</label><b>{{ scopeData.department || '—' }}</b></div>
          <div><label>上级 / 挂靠</label><b>{{ parentLabel(scopeData.parentUsername) }}</b></div>
          <div><label>状态</label><b>{{ scopeData.status === 'active' ? '启用' : '停用' }}</b></div>
          <div><label>下属</label><b>{{ (scopeData.subordinates || []).map((s: any) => s.username).join('、') || '—' }}</b></div>
          <div><label>关联站点</label><b>{{ relationText(scopeData.relatedStations) }}</b></div>
          <div><label>关联产品</label><b>{{ relationText(scopeData.relatedProducts) }}</b></div>
          <div><label>关联设备</label><b>{{ relationText(scopeData.relatedEquipment) }}</b></div>
          <div><label>备注</label><b>{{ scopeData.notes || '—' }}</b></div>
        </div>
        <div v-if="scopeData" class="perm-section">
          <label>角色权限</label>
          <div class="perm-chips">
            <span v-for="code in scopeData.permissions || []" :key="code" class="chip mono">{{ code }}</span>
            <span v-if="!(scopeData.permissions || []).length" class="mini">无</span>
          </div>
        </div>
        <div v-if="scopeData" class="perm-section">
          <label>模块授权</label>
          <div class="perm-chips">
            <span v-for="(value, key) in scopeData.moduleGrants || {}" :key="String(key)" class="chip">{{ key }}</span>
            <span v-if="!Object.keys(scopeData.moduleGrants || {}).length" class="mini">无</span>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn" type="button" @click="scopeOpen = false">关闭</button>
        </div>
      </div>
    </div>

    <div v-if="roleEditOpen" class="modal-mask" @click.self="roleEditOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <h3>变更角色</h3>
        <div v-if="roleEditError" class="msg err">{{ roleEditError }}</div>
        <div class="field">
          <label>人员</label>
          <b>{{ roleEditPerson?.name || roleEditPerson?.username }}（{{ roleEditPerson?.username }}）</b>
        </div>
        <div class="field">
          <label>当前角色</label>
          <b>{{ roleName(roleEditPerson?.role) }}</b>
        </div>
        <div class="field">
          <label>新角色</label>
          <select v-model="roleEditCode">
            <option value="">请选择角色</option>
            <option v-for="r in assignableRoles" :key="r.code" :value="r.code">{{ r.name }}（{{ r.code }}）</option>
          </select>
        </div>
        <p class="hint">只能分配当前账号有权下放的角色；变更会写入审计日志。</p>
        <div class="modal-foot">
          <button class="btn" type="button" @click="roleEditOpen = false">取消</button>
          <button class="btn primary" type="button" :disabled="roleEditSaving" @click="saveRole">
            {{ roleEditSaving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api, getUser } from '../api'
import { sharedPerms } from '../stores/permStore'
import { usePersonnel } from '../composables/usePersonnel'
import PersonOrgTree from '../components/PersonOrgTree.vue'
import ModuleAccessTree from '../components/ModuleAccessTree.vue'
import FixedModuleNotice from '../components/FixedModuleNotice.vue'
import RoleCombinationForm from '../components/RoleCombinationForm.vue'

const canView = computed(() => sharedPerms.value.some(p => p === 'person:manage' || p === 'system:user:manage' || p === 'system:role:manage'))
const canManage = computed(() => sharedPerms.value.some(p => p === 'system:user:manage' || p === 'system:role:manage'))
const canCreateRole = computed(() => sharedPerms.value.includes('system:role:manage'))
const DEFAULT_ROLE_KEY = 'mes_person_default_role'
const roleWindowOpen = ref(false)
const selectedExistingRole = ref('')
const roleNotice = ref('')
const { persons, loading, error, loadPersons } = usePersonnel()
const roles = ref<any[]>([])
const keyword = ref('')
const parentKeyword = ref('')
const treeSelected = ref({ position: '', role: '' })
const modal = ref('')
const formError = ref('')
const saving = ref(false)
const rolePermissions = ref<string[]>([])
const accessPerson = ref<any>(null)
const accessPermissions = ref<string[]>([])
const permissionError = ref('')
const permissionSaving = ref(false)
const detailOpen = ref(false)
const detailModule = ref<any>(null)
const detailSelected = ref<string[]>([])
const form = ref<any>(emptyForm())
const permissionTree = ref<any[]>([])
const positionEditOpen = ref(false)
const positionFrom = ref('')
const positionTo = ref('')
const positionError = ref('')
const positionSaving = ref(false)
const relationOptions = reactive<any>({ stations: [], products: [], equipment: [] })
const linkOpen = ref(false)
const linkPerson = ref<any>(null)
const linkParent = ref('')
const linkError = ref('')
const linkSaving = ref(false)
const scopeOpen = ref(false)
const scopeData = ref<any>(null)
const scopeError = ref('')
const roleEditOpen = ref(false)
const roleEditPerson = ref<any>(null)
const roleEditCode = ref('')
const roleEditError = ref('')
const roleEditSaving = ref(false)

// 可下放的角色：目标角色的权限点必须是当前账号已持有的权限的子集。
const assignableRoles = computed(() => roles.value.filter(r => r.code !== 'admin'))

const modalTitle = computed(() => ({
  create: '新增人员与登录账户', edit: '编辑人员信息', access: '编辑人员权限',
}[modal.value] || ''))
const modulePermOptions = [
  { code: 'dashboard:view', key: 'dashboard', name: '看板', path: '/dashboard' },
  { code: 'person:manage', key: 'person', name: '人员管理', path: '/person' },
  { code: 'machine:manage', key: 'machine', name: '设备管理', path: '/machine' },
  { code: 'material:manage', key: 'material', name: '物料管理', path: '/material' },
  { code: 'method:manage', key: 'method', name: '工艺管理', path: '/method' },
  { code: 'environment:manage', key: 'environment', name: '共享资料库', path: '/environment' },
]
const assignableModulePerms = computed(() => modulePermOptions.filter(item => sharedPerms.value.includes(item.code)))
const detailPermOptions = computed(() => {
  const rows: any[] = []
  const seen = new Set<string>()
  permissionTree.value.forEach((group: any) => {
    (group.children || []).forEach((node: any) => {
      const code = String(node.permission || '')
      if (!code || node.moduleKey !== detailModule.value?.key || seen.has(code)) return
      if (!sharedPerms.value.includes(code)) return
      seen.add(code)
      rows.push({ code, name: node.name || code, path: node.route || '' })
    })
  })
  return rows
})
const personAssignableCodes = computed(() => {
  const codes = new Set(modulePermOptions.map(item => item.code).filter(code => sharedPerms.value.includes(code)))
  permissionTree.value.forEach((group: any) => {
    (group.children || []).forEach((node: any) => {
      const code = String(node.permission || '')
      if (code && sharedPerms.value.includes(code)) codes.add(code)
    })
  })
  return Array.from(codes)
})
const selectedRoleLabel = computed(() => {
  const role = roles.value.find(r => r.code === form.value.role)
  return role ? `${role.name}（${role.code}）` : '请选择角色'
})

const filteredPersons = computed(() => persons.value.filter(p => {
  if (treeSelected.value.position && (p.position || '未分配岗位') !== treeSelected.value.position) return false
  if (treeSelected.value.role && (p.role || '未分配角色') !== treeSelected.value.role) return false
  const q = keyword.value.trim().toLowerCase()
  if (q && !`${p.name} ${p.username} ${p.position}`.toLowerCase().includes(q)) return false
  const pq = parentKeyword.value.trim().toLowerCase()
  if (pq && !parentLabel(p.parentUsername).toLowerCase().includes(pq)) return false
  return true
}))

function emptyForm() {
  return { username: '', password: '', name: '', role: '', position: '', parentUsername: getUser()?.username || '', status: 'active', relatedStations: [], relatedProducts: [], relatedEquipment: [], notes: '' }
}
const allParentOptions = computed(() => {
  const me = getUser()
  const rows = [...persons.value.map((p: any) => ({ username: p.username, name: p.name || p.username }))]
  if (me?.username && !rows.some(p => p.username === me.username)) rows.unshift({ username: me.username, name: me.name || me.username })
  return rows
})
const parentOptions = computed(() => allParentOptions.value.filter(p => p.username !== form.value.username))
const linkOptions = computed(() => allParentOptions.value.filter(p => p.username !== linkPerson.value?.username))
function parentLabel(username?: string) {
  if (!username) return '—'
  const hit = allParentOptions.value.find(p => p.username === username)
  return hit ? `${hit.name}（${hit.username}）` : username
}
function roleName(code?: string) { return roles.value.find(r => r.code === code)?.name || code || '—' }
function clearAccountFields() {
  form.value.username = ''
  form.value.password = ''
  formError.value = ''
}
function selectTree(value: { position: string; role: string }) { treeSelected.value = value }
function openPositionEdit(position: string) {
  positionFrom.value = position
  positionTo.value = position
  positionError.value = ''
  positionEditOpen.value = true
}
async function savePosition() {
  positionError.value = ''
  const next = positionTo.value.trim()
  if (!next) { positionError.value = '请输入新岗位名称'; return }
  if (next === positionFrom.value) { positionEditOpen.value = false; return }
  positionSaving.value = true
  try {
    await api.renamePersonPosition(positionFrom.value, next)
    if (treeSelected.value.position === positionFrom.value) treeSelected.value = { ...treeSelected.value, position: next }
    positionEditOpen.value = false
    await reload()
  } catch (e: any) {
    positionError.value = e.message || '岗位保存失败'
  } finally {
    positionSaving.value = false
  }
}
async function reload() { await loadPersons() }
async function onComboRoleCreated(role: any) {
  try { roles.value = await api.roles() } catch { roles.value = [] }
  applyRole(role.code, role.permissions || [])
  closeRoleWindow()
}

function readDefaultRole() {
  try { return localStorage.getItem(DEFAULT_ROLE_KEY) || '' } catch { return '' }
}
function saveDefaultRole(code: string) {
  try { localStorage.setItem(DEFAULT_ROLE_KEY, code) } catch { /* 本地存储不可用时忽略 */ }
}
function applyRole(code: string, permissions?: string[]) {
  form.value.role = code
  selectedExistingRole.value = code
  rolePermissions.value = permissions || roles.value.find(r => r.code === code)?.permissions || []
  saveDefaultRole(code)
  roleNotice.value = '已保存为默认角色并选中'
}
function openRoleWindow() {
  if (modal.value === 'edit') return
  selectedExistingRole.value = form.value.role || readDefaultRole()
  roleNotice.value = ''
  roleWindowOpen.value = true
}
function closeRoleWindow() {
  roleWindowOpen.value = false
}
function chooseExistingRole() {
  if (!selectedExistingRole.value) return
  applyRole(selectedExistingRole.value)
  closeRoleWindow()
}
function openCreate() {
  const defaultRole = readDefaultRole()
  form.value = { ...emptyForm(), role: roles.value.some(r => r.code === defaultRole) ? defaultRole : '' }
  formError.value = ''; roleNotice.value = ''; rolePermissions.value = []; modal.value = 'create'
}
function openEdit(p: any) {
  const person = { ...(p || {}) }
  delete person.phone
  delete person.department
  form.value = {
    ...emptyForm(), ...person, password: '',
    relatedStations: (person.relatedStations || []).map((item: any) => typeof item === 'string' ? item : item.code).filter(Boolean),
    relatedProducts: (person.relatedProducts || []).map((item: any) => typeof item === 'string' ? item : item.code).filter(Boolean),
    relatedEquipment: (person.relatedEquipment || []).map((item: any) => typeof item === 'string' ? item : item.code).filter(Boolean),
  }
  formError.value = ''; rolePermissions.value = p.permissions || []; modal.value = 'edit'
}
function linkPayload(p: any, parent: string) {
  return {
    username: p.username,
    name: p.name || p.username,
    role: p.role || '',
    department: p.department || '',
    position: p.position || '',
    parentUsername: parent,
    phone: p.phone || '',
    status: p.status || 'active',
    moduleGrants: p.moduleGrants || {},
    relatedStations: (p.relatedStations || []).map((item: any) => typeof item === 'string' ? item : item.code).filter(Boolean),
    relatedProducts: (p.relatedProducts || []).map((item: any) => typeof item === 'string' ? item : item.code).filter(Boolean),
    relatedEquipment: (p.relatedEquipment || []).map((item: any) => typeof item === 'string' ? item : item.code).filter(Boolean),
    notes: p.notes || '',
  }
}
function openLink(p: any) {
  linkPerson.value = p
  linkParent.value = p.parentUsername || ''
  linkError.value = ''
  linkOpen.value = true
}
async function saveLink() {
  if (!linkPerson.value) return
  linkError.value = ''
  linkSaving.value = true
  try {
    await api.updatePerson(linkPerson.value.username, linkPayload(linkPerson.value, linkParent.value))
    linkOpen.value = false
    await reload()
  } catch (e: any) {
    linkError.value = e.message || '挂靠保存失败'
  } finally {
    linkSaving.value = false
  }
}
async function unlink(p: any) {
  if (!p.parentUsername) return
  error.value = ''
  try {
    await api.updatePerson(p.username, linkPayload(p, ''))
    await reload()
  } catch (e: any) {
    error.value = e.message || '取消挂靠失败'
  }
}

async function openAccess(p: any) {
  accessPerson.value = p
  permissionError.value = ''
  const allowed = new Set(personAssignableCodes.value)
  accessPermissions.value = (p.permissions || []).filter((code: string) => allowed.has(code))
  modal.value = 'access'
  try {
    const r: any = await api.personPermissions(p.username)
    accessPermissions.value = (r.permissions || []).filter((code: string) => allowed.has(code))
  } catch { /* 保留列表中的权限缓存 */ }
}
function relationText(items: any[]) {
  if (!Array.isArray(items) || !items.length) return '—'
  return items.map(item => item?.name || item?.code || '').filter(Boolean).join('、')
}
async function openScope(p: any) {
  scopeError.value = ''
  scopeData.value = null
  scopeOpen.value = true
  try {
    scopeData.value = await api.personScope(p.username)
  } catch (e: any) {
    scopeError.value = e.message || '人员详情加载失败'
  }
}
function openRole(p: any) {
  roleEditError.value = ''
  roleEditPerson.value = p
  roleEditCode.value = p.role || ''
  roleEditOpen.value = true
}
async function saveRole() {
  if (!roleEditPerson.value) return
  const code = roleEditCode.value
  if (!code) { roleEditError.value = '请选择角色'; return }
  if (code === roleEditPerson.value.role) { roleEditOpen.value = false; return }
  roleEditError.value = ''
  roleEditSaving.value = true
  try {
    await api.setPersonRole(roleEditPerson.value.username, code)
    roleEditOpen.value = false
    await reload()
  } catch (e: any) {
    roleEditError.value = e.message || '角色变更失败'
  } finally {
    roleEditSaving.value = false
  }
}
function openPermissionDetail(item: any) {
  detailModule.value = item
  detailSelected.value = detailPermOptions.value
    .map(option => option.code)
    .filter(code => accessPermissions.value.includes(code))
  detailOpen.value = true
}
function savePermissionDetail() {
  if (!detailModule.value) return
  const current = new Set(accessPermissions.value)
  detailPermOptions.value.forEach(option => current.delete(option.code))
  detailSelected.value.forEach(code => current.add(code))
  if (detailSelected.value.length) current.add(detailModule.value.code)
  accessPermissions.value = Array.from(current)
  detailOpen.value = false
}
async function saveAccessPermissions() {
  if (!accessPerson.value) return
  permissionError.value = ''
  permissionSaving.value = true
  try {
    await api.setPersonPermissions(accessPerson.value.username, accessPermissions.value)
    modal.value = ''
    await reload()
  } catch (e: any) {
    permissionError.value = e.message || '权限保存失败'
  } finally {
    permissionSaving.value = false
  }
}

async function save() {
  formError.value = ''
  if (!form.value.name.trim()) { formError.value = '请输入姓名'; return }
  if (modal.value === 'create') {
    if (!form.value.username.trim()) { formError.value = '请输入登录用户名'; return }
    if (form.value.password.length < 6) { formError.value = '初始密码至少 6 位'; return }
    if (!form.value.role) { formError.value = '请选择角色'; return }
  } else if (form.value.password && form.value.password.length < 6) {
    formError.value = '重置密码至少 6 位，留空则不修改'
    return
  }
  saving.value = true
  try {
    const payload = { ...form.value }
    delete payload.phone
    delete payload.department
    if (modal.value === 'create') await api.createPerson(payload)
    else await api.updatePerson(payload.username, payload)
    modal.value = ''; await reload()
  } catch (e: any) { formError.value = e.message || '保存失败' }
  finally { saving.value = false }
}

watch(() => form.value.role, async (code) => {
  if (!code) { rolePermissions.value = []; return }
  try { rolePermissions.value = await api.rolePerms(code) } catch { rolePermissions.value = [] }
})

onMounted(async () => {
  if (!canView.value) return
  try {
    const tree: any = await api.functionTree()
    permissionTree.value = tree?.nodes || []
  } catch { permissionTree.value = [] }
  await reload()
  try { roles.value = await api.roles() } catch { roles.value = [] }
  try {
    const data: any = await api.relationOptions()
    relationOptions.stations = data.stations || []
    relationOptions.products = data.products || []
    relationOptions.equipment = data.equipment || []
  } catch { /* 选项加载失败不阻塞人员列表 */ }
})
</script>

<style scoped>
.person-page { max-width: 1180px; margin: 0 auto; }
.head { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.head h2 { font-size: 22px; }
.sub { color: var(--muted); font-size: 13px; margin-top: 6px; }
.row, .toolbar { display: flex; gap: 8px; flex-wrap: wrap; }
.person-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 12px; }
.tree-panel, .list-panel { background: var(--white); border: 1px solid var(--line); border-radius: 8px; padding: 12px; min-width: 0; }
.panel-title { font-weight: 700; margin-bottom: 8px; }
.toolbar { margin-bottom: 12px; }
.toolbar input { flex: 1; min-width: 180px; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--line); font-size: 13px; }
th { color: var(--muted); font-weight: 600; }
.empty { text-align: center; color: var(--muted); padding: 26px; }
.link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; padding: 0; }
.combo-section { border: 1px solid var(--tech-blue-line); background: var(--tech-blue-soft); border-radius: 8px; padding: 12px; margin: 0 0 12px; }
.combo-title { font-weight: 700; font-size: 13px; margin-bottom: 8px; }
.role-select { width: 100%; height: 38px; display: flex; align-items: center; justify-content: space-between; border: 1px solid var(--line); border-radius: 7px; padding: 0 10px; background: var(--white); color: var(--ink); cursor: pointer; text-align: left; }
.role-select:disabled { opacity: .55; cursor: not-allowed; }
.role-notice { display: inline-block; margin-top: 4px; color: var(--tech-blue); font-size: 11px; }
.role-window-mask { position: fixed; inset: 0; z-index: 120; display: grid; place-items: center; padding: 16px; background: rgba(4,8,18,.72); }
.role-window { width: min(720px, 100%); max-height: 88vh; overflow: auto; background: var(--white); border-radius: 10px; padding: 18px; }
.role-window-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 10px; }
.role-window-head h3 { font-size: 18px; }
.hint { color: var(--muted); font-size: 12px; margin: 0 0 12px; }
.grid2 { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }
.account-clear-row { display: flex; align-items: center; gap: 10px; margin: -2px 0 12px; font-size: 11px; color: var(--muted); }
.account-clear-row .link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; padding: 0; font-size: 12px; }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.modal-mask { position: fixed; inset: 0; background: rgba(4,8,18,.6); display: grid; place-items: center; z-index: 80; padding: 16px; }
.modal { width: 100%; max-width: 680px; max-height: min(90dvh, 880px); overflow: auto; background: var(--white); border-radius: 10px; padding: 20px; }
.position-modal, .link-modal { max-width: 420px; }
.modal h3 { margin-bottom: 14px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px; }
.module-perm-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
.module-perm-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; border: 1px solid var(--line); border-radius: 7px; padding: 9px 10px; }
.module-perm-item:hover { border-color: var(--tech-blue-line); background: var(--tech-blue-soft); }
.module-perm-main { display: flex; align-items: flex-start; gap: 8px; min-width: 0; cursor: pointer; }
.module-perm-item input { width: auto; margin-top: 2px; }
.module-perm-item span { display: grid; gap: 2px; min-width: 0; }
.module-perm-item b { font-size: 12px; }
.module-perm-item small { color: var(--muted); font-size: 10px; }
.detail-mask { z-index: 130; }
.detail-modal { width: min(680px, 100%); max-height: 86vh; overflow: auto; }
.info-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 16px; }
.info-grid > div { display: grid; gap: 3px; min-width: 0; }
.info-grid label { color: var(--muted); font-size: 11px; }
.info-grid b { font-size: 13px; word-break: break-all; }
.perm-section { margin-top: 12px; }
.perm-section > label { display: block; color: var(--muted); font-size: 11px; margin-bottom: 6px; }
.perm-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.perm-chips .chip { border: 1px solid var(--line); border-radius: 999px; padding: 3px 9px; font-size: 11px; background: var(--tech-blue-soft); }
@media (max-width: 680px) { .info-grid { grid-template-columns: 1fr; } }
.detail-perm-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
.detail-perm-item { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 7px; padding: 9px 10px; cursor: pointer; }
.detail-perm-item input { width: auto; }
.detail-perm-item span { display: grid; gap: 2px; min-width: 0; }
.detail-perm-item small { color: var(--muted); font-size: 10px; }
.btn.sm { padding: 5px 10px; font-size: 12px; }
.relation-block { border: 1px solid var(--line); border-radius: 7px; padding: 8px 10px; margin-top: 10px; }
.relation-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.relation-grid select { width: 100%; min-height: 76px; }
@media (max-width: 900px) { .person-layout { grid-template-columns: 1fr; } }
@media (max-width: 768px) { .head { flex-direction: column; } .grid2 { grid-template-columns: 1fr; } .module-perm-grid, .detail-perm-grid { grid-template-columns: 1fr; } }
</style>
