<template>
  <div class="site-wrap">
    <div class="card">
      <div class="head">
        <div>
          <h2>自定义站点</h2>
          <p class="sub">维护可访问站点、分组与访问流程；配置保存在服务端，保存后立即生效。</p>
        </div>
        <div class="row">
          <button class="btn" @click="router.push('/station')">返回过站</button>
          <button v-if="canManage" class="btn primary" @click="openCreateSite">新增站点</button>
        </div>
      </div>

      <div v-if="!canManage" class="msg err">当前账号无自定义站点管理权限。</div>
      <template v-else>
        <div v-if="error" class="msg err">{{ error }}</div>

        <div class="tabs">
          <button :class="{ active: tab === 'sites' }" @click="tab = 'sites'">站点列表</button>
          <button :class="{ active: tab === 'groups' }" @click="tab = 'groups'">分组管理</button>
          <button :class="{ active: tab === 'flows' }" @click="tab = 'flows'">访问流程</button>
        </div>

        <template v-if="tab === 'sites'">
          <div class="toolbar">
            <input v-model="keyword" placeholder="搜索站点名称 / URL / 描述" />
            <select v-model="groupFilter"><option value="">全部分组</option><option v-for="g in config.groups" :key="g.id" :value="g.id">{{ g.name }}</option></select>
            <button class="btn" @click="load">刷新</button>
          </div>
          <div class="site-grid">
            <div v-for="s in filteredSites" :key="s.id" class="site-card" :class="{ disabled: !s.enabled }">
              <div class="site-top">
                <span class="site-icon" :title="s.name">
                  <AppIcon v-if="hasIcon(s.icon)" :name="s.icon" :size="18" :label="s.name" />
                  <template v-else>{{ s.icon || '◇' }}</template>
                </span>
                <div class="site-name"><b>{{ s.name }}</b><small>{{ groupName(s.groupId) }}</small></div>
                <span class="tag" :class="s.enabled ? 'station_done' : 'failed'">{{ s.enabled ? '启用' : '停用' }}</span>
              </div>
              <p class="site-desc">{{ s.description || '暂无描述' }}</p>
              <div class="site-url mono">{{ s.url }}</div>
              <div class="site-meta">
                <span>顺序 {{ s.order }}</span>
                <span>跳转 {{ nextRuleLabel(s.flow?.nextRule) }}</span>
                <span>{{ accessSummary(s.access) }}</span>
              </div>
              <div class="site-actions">
                <button class="btn sm" @click="openSite(s)">打开</button>
                <button class="btn sm" @click="openEditSite(s)">编辑</button>
                <button class="btn sm danger" @click="removeSite(s)">删除</button>
              </div>
            </div>
            <div v-if="!filteredSites.length" class="empty-box">未找到匹配的站点</div>
          </div>
        </template>

        <template v-else-if="tab === 'groups'">
          <div class="toolbar"><button class="btn primary" @click="openCreateGroup">新增分组</button></div>
          <div class="table-scroll medium">
          <table>
            <thead><tr><th>分组</th><th>名称</th><th>描述</th><th>顺序</th><th>站点数</th><th style="text-align:right">操作</th></tr></thead>
            <tbody>
              <tr v-for="g in sortedGroups" :key="g.id">
                <td class="mono">{{ g.id }}</td><td>{{ g.name }}</td><td class="mini">{{ g.description || '—' }}</td>
                <td>{{ g.order }}</td><td>{{ config.sites.filter((s: any) => s.groupId === g.id).length }}</td>
                <td style="text-align:right"><button class="btn sm" @click="openEditGroup(g)">编辑</button> <button class="btn sm danger" @click="removeGroup(g)">删除</button></td>
              </tr>
            </tbody>
          </table>
          </div>
        </template>

        <template v-else-if="tab === 'flows'">
          <div class="toolbar"><button class="btn primary" @click="openCreateFlow">新增流程</button></div>
          <div v-for="f in config.flows" :key="f.id" class="flow-row">
            <div><b>{{ f.name }}</b><div class="mini mono">{{ f.id }}</div></div>
            <div class="mini">{{ f.description || '暂无描述' }}</div>
            <div class="mini">{{ (f.siteIds || []).map((id: string) => siteName(id)).join(' → ') || '未配置站点' }}</div>
            <div>{{ accessSummary(f.access) }}</div>
            <div class="site-actions">
              <button class="btn sm" @click="openEditFlow(f)">编辑</button>
              <button class="btn sm danger" @click="removeFlow(f)">删除</button>
            </div>
          </div>
          <div v-if="!config.flows.length" class="empty-box">暂无访问流程</div>
        </template>
      </template>
    </div>

    <div v-if="modal" class="modal-mask" @click.self="modal = ''">
      <div class="modal">
        <h3>{{ modalTitle }}</h3>
        <template v-if="modal === 'site'">
          <div class="field"><label>站点名称</label><input v-model="form.name" placeholder="如：质量看板" /></div>
          <div class="field"><label>URL</label><input v-model="form.url" placeholder="/wo 或 https://example.com" /></div>
          <div class="field"><label>图标</label><input v-model="form.icon" placeholder="单个字符，如 ◇" /></div>
          <div class="field"><label>分组</label><select v-model="form.groupId"><option value="">未分组</option><option v-for="g in config.groups" :key="g.id" :value="g.id">{{ g.name }}</option></select></div>
          <div class="field"><label>描述</label><textarea v-model="form.description" rows="2" /></div>
          <div class="grid2">
            <div class="field"><label>展示顺序</label><input v-model.number="form.order" type="number" /></div>
            <div class="field"><label>状态</label><select v-model="form.enabled"><option :value="true">启用</option><option :value="false">停用</option></select></div>
          </div>
          <div class="section-title">访问流程</div>
          <div class="grid2">
            <div class="field"><label>展示模式</label><select v-model="form.flow.mode"><option value="manual">手动打开</option><option value="sequence">按顺序展示</option></select></div>
            <div class="field"><label>流程顺序</label><input v-model.number="form.flow.order" type="number" /></div>
          </div>
          <div class="field"><label>跳转规则</label>
            <select v-model="form.flow.nextRule">
              <option value="none">不跳转</option><option value="sequence">同分组下一站</option>
              <option value="site">指定站点</option><option value="url">指定 URL</option>
            </select>
          </div>
          <div v-if="form.flow.nextRule === 'site'" class="field"><label>目标站点</label><select v-model="form.flow.nextSiteId"><option value="">请选择</option><option v-for="s in config.sites" :key="s.id" :value="s.id">{{ s.name }}</option></select></div>
          <div v-if="form.flow.nextRule === 'url'" class="field"><label>目标 URL</label><input v-model="form.flow.jumpUrl" /></div>
          <AccessFields :form="form.access" :roles="options.roles" :users="options.users" @update:form="form.access = $event" />
        </template>
        <template v-else-if="modal === 'group'">
          <div class="field"><label>分组名称</label><input v-model="form.name" /></div>
          <div class="field"><label>描述</label><textarea v-model="form.description" rows="2" /></div>
          <div class="field"><label>顺序</label><input v-model.number="form.order" type="number" /></div>
        </template>
        <template v-else-if="modal === 'flow'">
          <div class="field"><label>流程名称</label><input v-model="form.name" /></div>
          <div class="field"><label>描述</label><textarea v-model="form.description" rows="2" /></div>
          <div class="field"><label>站点顺序</label>
            <div class="flow-sites">
              <label v-for="s in config.sites" :key="s.id"><input type="checkbox" :value="s.id" v-model="form.siteIds" /> {{ s.name }}</label>
            </div>
          </div>
          <div class="grid2">
            <div class="field"><label>顺序</label><input v-model.number="form.order" type="number" /></div>
            <div class="field"><label>状态</label><select v-model="form.enabled"><option :value="true">启用</option><option :value="false">停用</option></select></div>
          </div>
          <AccessFields :form="form.access" :roles="options.roles" :users="options.users" @update:form="form.access = $event" />
        </template>
        <div v-if="formError" class="msg err">{{ formError }}</div>
        <div class="modal-foot"><button class="btn" @click="modal = ''">取消</button><button class="btn primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { AppIcon, hasIcon } from '../components/icons'
import { sharedPerms } from '../stores/permStore'

const AccessFields = defineComponent({
  props: { form: { type: Object, required: true }, roles: { type: Array, default: () => [] }, users: { type: Array, default: () => [] } },
  emits: ['update:form'],
  setup(props, { emit }) {
    const patch = (key: 'roles' | 'users', value: string[]) => {
      emit('update:form', { ...props.form, [key]: value })
    }
    return () => h('div', { class: 'access-fields' }, [
      h('div', { class: 'section-title' }, '访问权限'),
      h('label', { class: 'multi-label' }, '授权角色'),
      h('select', {
        multiple: true, value: props.form.roles || [],
        onChange: (e: Event) => patch('roles', Array.from((e.target as HTMLSelectElement).selectedOptions).map(o => o.value)),
      }, (props.roles as any[]).map(r => h('option', { key: r.value, value: r.value }, `${r.label}（${r.value}）`))),
      h('label', { class: 'multi-label' }, '授权用户'),
      h('select', {
        multiple: true, value: props.form.users || [],
        onChange: (e: Event) => patch('users', Array.from((e.target as HTMLSelectElement).selectedOptions).map(o => o.value)),
      }, (props.users as any[]).map(u => h('option', { key: u.value, value: u.value }, `${u.label}（${u.value}）`))),
      h('div', { class: 'mini' }, '留空表示所有账号可见；角色与用户命中任一即可访问。'),
    ])
  },
})

const router = useRouter()
const canManage = computed(() => sharedPerms.value.some(p => p === 'system:access:manage' || p === 'system:role:manage'))
const config = ref<any>({ groups: [], sites: [], flows: [], canManage: false })
const options = ref<any>({ roles: [], users: [] })
const tab = ref<'sites' | 'groups' | 'flows'>('sites')
const keyword = ref('')
const groupFilter = ref('')
const error = ref('')
const formError = ref('')
const saving = ref(false)
const modal = ref('')
const editingId = ref('')
const form = ref<any>({})

const modalTitle = computed(() => ({
  site: editingId.value ? '编辑站点' : '新增站点',
  group: editingId.value ? '编辑分组' : '新增分组',
  flow: editingId.value ? '编辑流程' : '新增流程',
}[modal.value] || ''))
const sortedGroups = computed(() => [...config.value.groups].sort((a: any, b: any) => (a.order || 0) - (b.order || 0)))
const filteredSites = computed(() => config.value.sites.filter((s: any) => {
  if (groupFilter.value && s.groupId !== groupFilter.value) return false
  const q = keyword.value.trim().toLowerCase()
  if (!q) return true
  return `${s.name} ${s.url} ${s.description || ''}`.toLowerCase().includes(q)
}).sort((a: any, b: any) => (a.order || 0) - (b.order || 0)))

function groupName(id: string) { return config.value.groups.find((g: any) => g.id === id)?.name || '未分组' }
function siteName(id: string) { return config.value.sites.find((s: any) => s.id === id)?.name || id }
function accessSummary(access: any) {
  const roles = access?.roles || []; const users = access?.users || []
  if (!roles.length && !users.length) return '全部可见'
  return `角色${roles.length} / 用户${users.length}`
}
function nextRuleLabel(rule?: string) {
  return ({ none: '不跳转', sequence: '顺序', site: '指定站点', url: '指定URL' } as any)[rule || 'none'] || '不跳转'
}
function fmt(v?: string) { return v ? new Date(v).toLocaleString('zh-CN') : '—' }

async function load() {
  error.value = ''
  try {
    config.value = await api.customSites()
    if (config.value.canManage) {
      const o = await api.accessOptions()
      options.value = { roles: o.roles || [], users: o.users || [] }
    }
  } catch (e: any) { error.value = e.message || '加载失败' }
}
function openCreateSite() {
  editingId.value = ''; modal.value = 'site'; formError.value = ''
  form.value = { name: '', url: '', description: '', icon: '◇', groupId: '', order: config.value.sites.length + 1, enabled: true, access: { roles: [], users: [] }, flow: { mode: 'manual', order: 1, nextRule: 'none', nextSiteId: '', jumpUrl: '' } }
}
function openEditSite(s: any) {
  editingId.value = s.id; modal.value = 'site'; formError.value = ''
  form.value = JSON.parse(JSON.stringify({ ...s, access: s.access || { roles: [], users: [] }, flow: s.flow || {} }))
}
function openCreateGroup() {
  editingId.value = ''; modal.value = 'group'; formError.value = ''
  form.value = { name: '', description: '', order: config.value.groups.length + 1 }
}
function openEditGroup(g: any) { editingId.value = g.id; modal.value = 'group'; formError.value = ''; form.value = { ...g } }
function openCreateFlow() {
  editingId.value = ''; modal.value = 'flow'; formError.value = ''
  form.value = { name: '', description: '', siteIds: [], access: { roles: [], users: [] }, enabled: true, order: config.value.flows.length + 1 }
}
function openEditFlow(f: any) { editingId.value = f.id; modal.value = 'flow'; formError.value = ''; form.value = JSON.parse(JSON.stringify(f)) }
function openSite(s: any) {
  const url = s.url.startsWith('http') ? s.url : s.url
  window.open(url, '_blank')
}

async function removeSite(s: any) {
  if (!confirm(`确认删除站点 ${s.name}？`)) return
  try { await api.deleteCustomSite(s.id); await load() } catch (e: any) { error.value = e.message }
}
async function removeGroup(g: any) {
  if (!confirm(`确认删除分组 ${g.name}？`)) return
  try { await api.deleteSiteGroup(g.id); await load() } catch (e: any) { error.value = e.message }
}
async function removeFlow(f: any) {
  if (!confirm(`确认删除流程 ${f.name}？`)) return
  try { await api.deleteSiteFlow(f.id); await load() } catch (e: any) { error.value = e.message }
}

async function save() {
  formError.value = ''
  if (!form.value.name?.trim()) { formError.value = '名称不能为空'; return }
  if (modal.value === 'site' && !form.value.url?.trim()) { formError.value = 'URL 不能为空'; return }
  saving.value = true
  try {
    if (modal.value === 'site') {
      if (editingId.value) await api.updateCustomSite(editingId.value, form.value)
      else await api.createCustomSite(form.value)
    } else if (modal.value === 'group') {
      if (editingId.value) await api.updateSiteGroup(editingId.value, form.value)
      else await api.createSiteGroup(form.value)
    } else {
      if (editingId.value) await api.updateSiteFlow(editingId.value, form.value)
      else await api.createSiteFlow(form.value)
    }
    modal.value = ''; await load()
  } catch (e: any) { formError.value = e.message || '保存失败' }
  finally { saving.value = false }
}

onMounted(() => { if (canManage.value) void load() })
</script>

<style scoped>
.site-wrap { max-width: 1180px; margin: 0 auto; }
.head { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--line); margin-bottom: 14px; }
.tabs button { border: 0; background: transparent; padding: 8px 14px; color: var(--muted); cursor: pointer; }
.tabs button.active { color: var(--red); border-bottom: 2px solid var(--red); font-weight: 600; }
.site-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr)); gap: 12px; }
.site-card { border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; }
.site-card.disabled { opacity: .6; }
.site-top { display: flex; align-items: center; gap: 10px; }
.site-icon { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 8px; background: var(--tech-blue-soft); color: var(--tech-blue); font-size: 18px; font-weight: 700; }
.site-name { flex: 1; display: flex; flex-direction: column; }
.site-name small { color: var(--muted); }
.site-desc { font-size: 12px; color: var(--gray); min-height: 32px; margin: 12px 0 8px; line-height: 1.5; }
.site-url { font-size: 12px; color: var(--tech-blue); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.site-meta { display: flex; gap: 10px; flex-wrap: wrap; font-size: 11px; color: var(--muted); margin-top: 10px; }
.site-actions { display: flex; gap: 6px; margin-top: 12px; }
.empty-box { padding: 28px; text-align: center; color: var(--muted); border: 1px dashed var(--line); border-radius: 8px; }
.flow-row { display: grid; grid-template-columns: 1.2fr 1.4fr 2fr 1fr auto; gap: 12px; align-items: center; border-bottom: 1px solid var(--line); padding: 10px 0; }
.grid2 { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; }
.section-title { font-weight: 700; color: var(--ink); margin: 14px 0 8px; }
.multi-label { display: block; color: var(--muted); font-size: 12px; margin: 8px 0 4px; }
select[multiple] { min-height: 88px; }
.flow-sites { display: flex; gap: 10px; flex-wrap: wrap; }
.flow-sites label { display: inline-flex; gap: 5px; align-items: center; }
.flow-sites input { width: auto; }
.modal-mask { position: fixed; inset: 0; background: rgba(4,8,18,.6); display: grid; place-items: center; z-index: 80; padding: 16px; }
.modal { width: 100%; max-width: 620px; max-height: min(90dvh, 860px); overflow: auto; background: var(--white); border-radius: 10px; padding: 20px; }
.modal h3 { margin-bottom: 16px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
@media (max-width: 1024px) { .flow-row { grid-template-columns: 1fr 1fr; } }
@media (max-width: 900px) { .head { flex-direction: column; } .tabs { overflow-x: auto; } .tabs button { flex: none; } }
@media (max-width: 768px) { .flow-row { grid-template-columns: 1fr; } .grid2 { grid-template-columns: 1fr; } }
</style>
