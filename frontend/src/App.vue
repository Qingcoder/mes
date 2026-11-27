<template>
  <div v-if="isLogin" class="login-page">
    <!-- 全局深色科技背景 -->
    <div class="hud-grid"></div>
    <div class="hud-corners"><i></i><i></i><i></i><i></i></div>

    <!-- 左上角品牌区：戴盟 logo + 生产管理平台 -->
    <div class="login-top-brand">
      <DaimonLogo class="login-top-logo" />
      <div class="brand-title">MES 生产管理平台</div>
    </div>

    <!-- 反应堆环作为背景水印（不占布局，居中偏后） -->
    <div class="bg-core">
      <div class="hud">
        <i class="ring r1"></i>
        <i class="ring r2"></i>
        <i class="ring r3"></i>
        <i class="ring r4"></i>
        <i class="ring r5"></i>
        <i class="ticks"></i>
        <i class="arc-red"></i>
        <i class="arc-blue"></i>
        <i class="core-disc"></i>
        <i class="halo"></i>
      </div>
    </div>

    <!-- 居中登录卡 -->
    <div class="login-center"><router-view /></div>

    <div class="foot">戴盟（深圳）机器人科技有限公司<span class="version-mark"> · V1.0</span></div>
  </div>

  <!-- 扫码确认页：自带背景，裸渲染不套布局 -->
  <router-view v-else-if="isApprove" />

  <!-- 验证阶段独立页：只展示入口与创建角色，不套后台布局 -->
  <router-view v-else-if="isStandalone" />

  <!-- 专注作业页：只保留过站与详情，隐藏其他前端入口 -->
  <div v-else-if="isFocus" class="focus-app">
    <div class="focus-actions">
      <span class="focus-role">{{ roleViewLabel }}</span>
      <button v-if="route.path === '/station'" class="focus-link" @click="router.push('/sn-detail')">详情</button>
      <button v-else class="focus-link" @click="router.push('/station')">过站</button>
      <button v-if="canManageAccess && route.path !== '/site-manage'" class="focus-link" @click="router.push('/site-manage')">站点</button>
      <button v-if="canManageAccess && route.path !== '/access-control'" class="focus-link" @click="router.push('/access-control')">权限</button>
      <button class="focus-link" @click="logout">退出</button>
    </div>
    <main class="focus-content">
      <div v-if="route.query.denied" class="msg err">无权限访问：{{ route.query.denied }}</div>
      <router-view />
    </main>
  </div>

  <div v-else class="app">
    <aside class="sidebar">
      <div class="brand">
        <span class="mark">D</span>
        <b>戴盟 MES</b>
        <small class="version-mark">生产管理平台 V1.0</small>
      </div>
      <nav class="nav">
        <div v-for="group in menuGroups" :key="group.name" class="nav-group">
          <div v-if="group.name !== '核心模块' && group.name !== '人机料法环'" class="nav-group-title">{{ group.name }}</div>
          <router-link v-for="m in group.items" :key="m.path" class="nav-item" :to="m.path" active-class="active" :title="m.label"><AppIcon v-if="m.icon && !m.hideIcon" :name="m.icon" :size="18" :label="m.label" decorative /><span>{{ m.label }}</span></router-link>
        </div>
      </nav>
      <div class="side-foot">戴盟（深圳）机器人科技有限公司<br>数据存于本机 · 手机浏览器访问</div>
    </aside>
    <div class="main">
      <header class="topbar">
        <h1>{{ title }}</h1>
        <span class="role-badge" :class="roleView">{{ roleViewLabel }}</span>
        <div class="sep"></div>
        <div v-if="canSearchAny" class="global-search" @click.stop>
          <div class="gs-box" :class="{ active: searchOpen, 'no-clear': !searchText }">
            <span class="gs-icon"><AppIcon name="search" :size="16" label="全局搜索" /></span>
            <input v-model="searchText" class="gs-input" :disabled="!canSearchAny"
                   :placeholder="canSearchAny ? '搜索产品 / 人员 / 站点 / 工单 / SN / 箱号' : '当前角色无可用搜索范围'"
                   @focus="searchOpen = true" @keydown.enter.prevent="selectFirstResult" @keydown.esc="closeSearch" />
            <span v-if="!isDesktop" class="gs-scan" :class="{ disabled: !canSearchAny }" role="button" tabindex="0"
                  :aria-disabled="!canSearchAny" title="应用内扫码" aria-label="应用内扫码"
                  @click.stop="openScanner" @keydown.enter.prevent="openScanner" @keydown.space.prevent="openScanner"><AppIcon name="scan" :size="17" label="应用内扫码" decorative /></span>
            <span v-if="searchText" class="gs-clear" role="button" tabindex="0" title="清空" aria-label="清空搜索内容"
                  @click.stop="clearSearch" @keydown.enter.prevent="clearSearch" @keydown.space.prevent="clearSearch">✕</span>
          </div>
          <div v-if="searchOpen && searchText" class="gs-panel">
            <div class="gs-filters">
              <button v-for="t in availableSearchTypes" :key="t.value" :class="{ active: searchType === t.value }" @click="setSearchType(t.value)">{{ t.label }}</button>
            </div>
            <div v-if="searchLoading" class="gs-state">搜索中…</div>
            <div v-else-if="searchError" class="gs-state err">{{ searchError }}</div>
            <template v-else-if="searchItems.length">
              <div v-for="g in groupedResults" :key="g.type" class="gs-group">
                <div class="gs-group-title">{{ g.label }} <span>{{ g.items.length }}</span></div>
                <button v-for="it in g.items" :key="it.type + it.id" class="gs-item" @click="openSearchResult(it)">
                  <span class="gs-item-main"><b>{{ it.title }}</b><small>{{ it.subtitle }}</small></span>
                  <span class="gs-badge">{{ it.badge }}</span>
                </button>
              </div>
            </template>
            <div v-else class="gs-state empty">未找到与“{{ searchText }}”匹配的对象</div>
          </div>
        </div>
        <!-- 角色菜单：头像 + 姓名 + 角色徽标，点击展开详情 -->
        <div class="user-menu">
          <button class="user-trigger" @click="userOpen = !userOpen">
            <span class="avatar">{{ user?.avatar || (user?.name || '用')[0] }}</span>
            <span class="user-meta">
              <b>{{ user?.name || '未登录' }}</b>
              <small>{{ roleLabel }}</small>
            </span>
            <span class="caret" :class="{ open: userOpen }">▾</span>
          </button>
          <div v-if="userOpen" class="user-dropdown" @click.stop>
            <div class="ud-head">
              <span class="avatar lg">{{ (user?.name || '用')[0] }}</span>
              <div>
                <b>{{ user?.name || '未登录' }}</b>
                <small>@{{ user?.username || '—' }}</small>
              </div>
            </div>
            <div class="ud-row"><span>账号</span><b class="mono">{{ user?.username || '—' }}</b></div>
            <div class="ud-row"><span>角色</span><b>{{ roleLabel }}</b></div>
            <div class="ud-row"><span>页面视图</span><b>{{ roleViewLabel }}</b></div>
            <div class="ud-row"><span>身份标识</span><b class="mono">{{ user?.role || '—' }}</b></div>
            <div class="ud-row"><span>系统</span><b>戴盟 MES<span class="version-mark"> · V1.0</span></b></div>
            <button class="ud-action" type="button" @click="accountOpen = true">个人资料 / 修改密码</button>
            <div v-if="previewRole" class="ud-row"><span>界面预览角色</span><b>{{ previewRoleLabel }}</b></div>
            <div v-if="canSwitchRole && roles.length" class="ud-role-switch">
              <span>切换角色（测试）</span>
              <div class="role-chips">
                <button v-for="r in roles" :key="r.code" :class="{ active: (previewRole || user?.role) === r.code }" @click="switchRole(r.code)">{{ r.name }}</button>
              </div>
              <small>仅切换当前界面预览，账号身份与身份标识始终显示真实登录账号</small>
              <button v-if="previewRole" class="ud-restore" @click="restoreAccountRole">恢复账号角色</button>
            </div>
            <button class="ud-logout" @click="logout">退出登录</button>
          </div>
        </div>
      </header>
      <main class="content">
        <div v-if="configError" class="msg err config-error">路由权限配置错误：{{ configError }}</div>
        <router-view />
      </main>
    </div>
    <InAppScanner v-if="!isDesktop" ref="scannerRef" @result="onSearchScanResult" />
    <AccountProfileDialog
      :open="accountOpen"
      :user="user"
      :role-label="roleLabel"
      @close="accountOpen = false; userOpen = false"
      @updated="onAccountUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  api, clearToken, getToken, getUser, getPermissions, setPermissions, setUser,
  setPreviewRole, getPreviewRole, clearPreviewRole, globalSearch,
} from './api'
import DaimonLogo from './components/DaimonLogo.vue'
import InAppScanner from './components/InAppScanner.vue'
import AccountProfileDialog from './components/AccountProfileDialog.vue'
import { AppIcon } from './components/icons'
import {
  MENU_ROUTES, findAppRoute, validateRoutePermissions, firstAllowedPath as firstAllowedPathFor,
  SEARCH_TYPES, searchTypeAllowed, allowedSearchTypes,
} from './router/routeConfig'
import { sharedPerms as myPerms, setSharedPerms } from './stores/permStore'
import { useDesktopMode } from './utils/device'
import {
  ROLE_VIEW_LABEL, canManageAccess as hasAccessManagePerm,
  defaultPathFor, hasPerm, roleViewOf, routeAllowsView,
} from './utils/permission'

const route = useRoute()
const router = useRouter()
const { isDesktop } = useDesktopMode()
const isLogin = computed(() => route.path === '/login')
const isApprove = computed(() => route.path === '/scan-approve')
const isStandalone = computed(() => route.path === '/entry' || route.path === '/create-role')
const roleView = computed(() => roleViewOf(user.value?.role || '', myPerms.value))
const roleViewLabel = computed(() => ROLE_VIEW_LABEL[roleView.value])
const isAdminConsole = computed(() => roleView.value === 'admin')
const isFocus = computed(() => !!findAppRoute(route.path)?.focus && !isAdminConsole.value)
const canManageAccess = computed(() => hasAccessManagePerm(myPerms.value))
const canSwitchRole = computed(() => hasPerm(myPerms.value, 'system:role:manage') || user.value?.role === 'admin')
const title = computed(() => findAppRoute(route.path)?.label || '戴盟 MES 生产管理平台')
const user = ref(getUser())
const previewRole = ref(getPreviewRole())
const userOpen = ref(false)
const accountOpen = ref(false)
watch(() => route.path, () => {
  user.value = getUser()
  setSharedPerms(getPermissions())
}, { immediate: true })

const roles = ref<any[]>([])
const configError = ref('')
// 按 group 分组、order 排序，无权限的菜单项和整组都会被过滤掉。
const menuGroups = computed(() => {
  const allowed = MENU_ROUTES.filter(r =>
    (!r.permission || myPerms.value.includes(r.permission)) && routeAllowsView(r.view, roleView.value),
  )
  const groupMap = new Map<string, typeof allowed>()
  allowed.forEach(r => {
    const g = r.group || '其他'
    if (!groupMap.has(g)) groupMap.set(g, [])
    groupMap.get(g)!.push(r)
  })
  return Array.from(groupMap, ([name, items]) => {
    const sorted = [...items].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
    return {
      name,
      order: sorted[0]?.order ?? 0,
      items: sorted.map(r => ({ path: r.path, label: r.label || r.name, icon: r.icon || '·', hideIcon: !!(r as any).hideIcon, perm: r.permission || '' })),
    }
  }).sort((a, b) => a.order - b.order)
})
// 扁平列表供角色切换后决定跳转的首页，保持与分组菜单一致。
const visibleNav = computed(() => menuGroups.value.flatMap(g => g.items))

async function refreshPermissions() {
  try {
    const me: any = await api.myPermissions()
    setUser({ username: me.username, name: me.name, role: me.role, avatar: me.avatar || getUser()?.avatar || '' })
    user.value = getUser()
    setPermissions(me.permissions || []); setSharedPerms(me.permissions || [])
    if (!currentSearchTypeAllowed()) searchType.value = 'all'
  } catch { /* 保留已有权限缓存 */ }
}
async function validateConfigWithServer() {
  try {
    const perms = await api.permissions()
    const missing = validateRoutePermissions((perms || []).map((p: any) => p.code))
    if (missing.length) {
      configError.value = `路由权限码不在权限目录中：${missing.join('；')}`
      console.error('[route-config] ' + configError.value)
    }
  } catch { /* 权限目录暂不可用时保留静态配置校验结果 */ }
}

async function switchRole(code: string) {
  try {
    const perms = await api.rolePerms(code)
    setPermissions(perms); setSharedPerms(perms)
    if (!currentSearchTypeAllowed()) searchType.value = 'all'
    setPreviewRole(code === user.value?.role ? '' : code)
    previewRole.value = getPreviewRole()
    userOpen.value = false
    const view = roleViewOf(code, perms)
    router.push(defaultPathFor(view, perms, firstAllowedPathFor(perms)))
  } catch { /* 忽略切换失败 */ }
}

// 搜索类型权限统一从 routeConfig 读取，复用“路由 → 权限”绑定。
function currentSearchTypeAllowed(): boolean {
  const t = SEARCH_TYPES.find(t => t.value === searchType.value) || SEARCH_TYPES[0]
  return searchTypeAllowed(t, myPerms.value)
}
const availableSearchTypes = computed(() => allowedSearchTypes(myPerms.value))
const canSearchAny = computed(() => availableSearchTypes.value.some(t => t.value !== 'all'))
const searchText = ref('')
const searchType = ref('all')
const searchOpen = ref(false)
const searchLoading = ref(false)
const searchError = ref('')
const searchItems = ref<any[]>([])
const scannerRef = ref<any>(null)
let searchTimer: ReturnType<typeof setTimeout> | null = null

function openScanner() {
  if (isDesktop.value || !canSearchAny.value) return
  searchOpen.value = false
  scannerRef.value?.open()
}
async function onSearchScanResult(payload: { text: string; format: string }) {
  const text = (payload?.text || '').trim()
  if (!text) return
  searchText.value = text
  searchType.value = /^[A-Z0-9]{16}$/.test(text) && availableSearchTypes.value.some(t => t.value === 'sn')
    ? 'sn'
    : /^(WO|RW|AS)-/i.test(text) && availableSearchTypes.value.some(t => t.value === 'wo')
      ? 'wo'
      : 'all'
  searchOpen.value = true
  await runSearch()
}

const groupedResults = computed(() => {
  const map = new Map<string, any[]>()
  searchItems.value.forEach(it => {
    if (!map.has(it.type)) map.set(it.type, [])
    map.get(it.type)!.push(it)
  })
  return Array.from(map, ([type, items]) => ({ type, label: SEARCH_TYPES.find(t => t.value === type)?.label || type, items }))
})

async function runSearch() {
  const q = searchText.value.trim()
  if (!q) { searchItems.value = []; searchError.value = ''; return }
  if (!canSearchAny.value || !currentSearchTypeAllowed()) {
    searchError.value = '当前角色无权限搜索该类型'; searchItems.value = []; return
  }
  searchLoading.value = true; searchError.value = ''
  try {
    const r: any = await globalSearch(q, searchType.value)
    searchItems.value = r.items || []
  } catch (e: any) { searchError.value = e.message; searchItems.value = [] }
  finally { searchLoading.value = false }
}
function setSearchType(t: string) { searchType.value = t; runSearch() }
function clearSearch() { searchText.value = ''; searchItems.value = []; searchError.value = '' }
function closeSearch() { searchOpen.value = false }
function openSearchResult(it: any) {
  router.push({ path: it.route, query: it.query || {} })
  closeSearch(); clearSearch()
}
function selectFirstResult() {
  const first = groupedResults.value[0]?.items?.[0]
  if (first) openSearchResult(first)
}
watch(searchText, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(runSearch, 220)
})

function roleNameOf(code: string): string {
  if (!code) return '未分配角色'
  return roles.value.find(r => r.code === code)?.name
    || (code === 'admin' ? '系统管理员' : code)
}
const roleLabel = computed(() => roleNameOf(user.value?.role || ''))
function onAccountUpdated() {
  user.value = getUser()
  void refreshPermissions()
}
const previewRoleLabel = computed(() => roleNameOf(previewRole.value))
function restoreAccountRole() {
  clearPreviewRole(); previewRole.value = ''
  void refreshPermissions().then(() => {
    const view = roleViewOf(user.value?.role || '', myPerms.value)
    router.push(defaultPathFor(view, myPerms.value, firstAllowedPathFor(myPerms.value)))
  })
}
function logout() { clearToken(); previewRole.value = ''; userOpen.value = false; router.push('/login') }
function onUnauthorized() {
  clearToken(); previewRole.value = ''; userOpen.value = false; accountOpen.value = false
  user.value = null; setSharedPerms([])
  if (route.path !== '/login') router.push('/login')
}
function onDocClick(e: MouseEvent) {
  const el = e.target as HTMLElement
  if (!el.closest('.user-menu')) userOpen.value = false
  if (!el.closest('.global-search')) searchOpen.value = false
}
onMounted(async () => {
  document.addEventListener('click', onDocClick)
  window.addEventListener('mes-unauthorized', onUnauthorized)
  if (getToken()) {
    await validateConfigWithServer()
    clearPreviewRole(); previewRole.value = ''
    await refreshPermissions()
    try { roles.value = await api.roles() } catch { roles.value = [] }
  }
})
onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  window.removeEventListener('mes-unauthorized', onUnauthorized)
  if (searchTimer) clearTimeout(searchTimer)
})
</script>
