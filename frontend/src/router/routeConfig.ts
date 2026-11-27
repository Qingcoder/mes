import type { Component } from 'vue'
import type { RouteView } from '../utils/permission'
import { fixedModuleByKey } from '../config/fixedModules'
import Login from '../views/Login.vue'
import ScanApprove from '../views/ScanApprove.vue'
import WO from '../views/WO.vue'
import Station from '../views/Station.vue'
import Pack from '../views/Pack.vue'
import Query from '../views/Query.vue'
import RoleManage from '../views/RoleManage.vue'
import SnDetail from '../views/SnDetail.vue'
import StationDetail from '../views/StationDetail.vue'
import AccessManage from '../views/AccessManage.vue'
import SiteManage from '../views/SiteManage.vue'
import DomainModuleView from '../views/DomainModuleView.vue'
import PersonManage from '../views/PersonManage.vue'
import RoleCreateView from '../views/RoleCreateView.vue'
import HomeRedirect from '../views/HomeRedirect.vue'
import MethodDesign from '../views/MethodDesign.vue'
import ProductInfo from '../views/ProductInfo.vue'
import SnLibrary from '../views/SnLibrary.vue'
import QualityDashboard from '../views/QualityDashboard.vue'

export interface StationRouteConfig {
  flowStations: string[]
  repairStation: { id: string; name: string; returnStation?: string }
  assignPolicy: 'first' | 'pendingFirst'
  snPoolScope: 'workOrder'
  failCodeScope: 'station'
}

export interface AppRouteConfig {
  path: string
  name: string
  component?: Component
  redirect?: string
  label?: string
  icon?: string
  permission?: string
  public?: boolean
  menu?: boolean
  /** 所属导航分组 key（见 NAV_GROUPS）；菜单项必须归属一个已定义的分组 */
  group?: string
  /** 父级菜单路由 path：挂到父项下形成树；没有真实从属关系的菜单项一律平铺 */
  parent?: string
  order?: number
  station?: StationRouteConfig
  focus?: boolean
  view?: RouteView
  // 隐藏备用：保留路由与组件，不从代码中删除，不生成侧边栏入口。
  backup?: boolean
  // 固定占位模块：入口和路由长期保留，内容随需求逐步迭代。
  fixed?: boolean
  hideIcon?: boolean
  description?: string
}

/** 导航分组定义：顺序、默认展开状态、可见性权限要求。 */
export interface NavGroupConfig {
  key: string
  label: string
  /** 分组顺序，数字小的在前 */
  order: number
  /** 默认折叠；用户手动切换后的状态会覆盖它并被记住 */
  collapsed?: boolean
  /** 可见性要求：用户至少要有一个以此为前缀的权限码，否则整组不显示 */
  requirePermPrefix?: string
}

// 导航分组（唯一数据源）：现场作业 → 生产主管 → 配置中心
export const NAV_GROUPS: NavGroupConfig[] = [
  { key: 'ops', label: '现场作业', order: 1 },
  { key: 'supervisor', label: '生产主管', order: 2 },
  { key: 'config', label: '配置中心', order: 3, collapsed: true, requirePermPrefix: 'system:' },
]

// 站点作业配置作为 /station 路由的一部分，不携带任何操作人角色字段。
export const STATION_ROUTE_CONFIG: StationRouteConfig = {
  flowStations: ['OP10', 'OP20'],
  repairStation: { id: 'R100', name: '维修站' },
  assignPolicy: 'first',
  snPoolScope: 'workOrder',
  failCodeScope: 'station',
}

const fixedDashboard = fixedModuleByKey('dashboard')!
const fixedPerson = fixedModuleByKey('person')!
const fixedMachine = fixedModuleByKey('machine')!
const fixedMaterial = fixedModuleByKey('material')!
const fixedMethod = fixedModuleByKey('method')!
const fixedEnvironment = fixedModuleByKey('environment')!

// 唯一数据源：路由注册、菜单生成、权限校验全部从这里读取。
export const APP_ROUTES: AppRouteConfig[] = [
  { path: '/', name: 'root', component: HomeRedirect, public: true },
  { path: '/entry', name: 'entry', redirect: '/login', public: true },
  { path: '/create-role', name: 'createRole', component: RoleCreateView, permission: 'system:role:manage', menu: false },
  { path: '/product-info', name: 'productInfo', component: ProductInfo, label: '产品资料', icon: 'material', permission: 'wo:view', menu: true, group: 'config', parent: '/material', order: 11, view: 'shared', backup: true },
  { path: '/sn-library', name: 'snLibrary', component: SnLibrary, label: 'SN 库', icon: 'sn', permission: 'wo:view', menu: true, group: 'config', parent: '/material', order: 12, view: 'shared', backup: true },
  { path: '/login', name: 'login', component: Login, public: true },
  { path: '/method/station/:code', name: 'methodStation', component: StationDetail, permission: 'method:manage', menu: false },
  { path: '/scan-approve', name: 'scanApprove', component: ScanApprove, public: true },
  { path: '/wo', name: 'wo', component: WO, label: '工单管理', icon: 'wo', permission: 'wo:view', menu: true, group: 'supervisor', order: 10, view: 'shared', backup: true },
  { path: '/station', name: 'station', component: Station, label: '站点作业', icon: 'station', permission: 'station:op', menu: true, group: 'ops', order: 30, station: STATION_ROUTE_CONFIG, focus: true, view: 'shared', backup: true },
  { path: '/sn-detail', name: 'snDetail', component: SnDetail, label: 'SN 详情', permission: 'station:op', menu: false, group: 'ops', focus: true, view: 'shared', backup: true },
  { path: '/access-control', name: 'accessControl', component: AccessManage, label: '站点流程权限', icon: 'access', permission: 'system:access:manage', menu: true, group: 'config', parent: '/method', order: 21, view: 'shared', backup: true },
  { path: '/site-manage', name: 'siteManage', component: SiteManage, label: '自定义站点', icon: 'site', permission: 'system:access:manage', menu: true, group: 'config', parent: '/method', order: 20, view: 'shared', backup: true },
  { path: '/pack', name: 'pack', component: Pack, label: '包装管理', icon: 'pack', permission: 'pack:op', menu: true, group: 'ops', order: 31, view: 'shared', backup: true },
  { path: '/query', name: 'query', component: Query, label: '数据追溯', icon: 'query', permission: 'query:view', menu: true, group: 'ops', order: 32, view: 'shared', backup: true },
  { path: '/roles', name: 'roles', component: RoleManage, label: '权限管理', icon: 'role', permission: 'system:role:manage', menu: true, group: 'config', order: 40, view: 'shared', backup: true },
  { path: fixedDashboard.route, name: fixedDashboard.key, component: QualityDashboard, label: fixedDashboard.label, icon: fixedDashboard.icon || '•', permission: fixedDashboard.permission, menu: true, group: 'supervisor', order: 1, view: 'shared', backup: true, fixed: true, hideIcon: !fixedDashboard.icon, description: fixedDashboard.description },
  { path: fixedPerson.route, name: fixedPerson.key, component: PersonManage, label: fixedPerson.label, icon: fixedPerson.icon || '•', permission: fixedPerson.permission, menu: true, group: 'config', order: 2, view: 'shared', backup: true, fixed: true, hideIcon: !fixedPerson.icon, description: fixedPerson.description },
  { path: fixedMachine.route, name: fixedMachine.key, component: DomainModuleView, label: fixedMachine.label, icon: fixedMachine.icon || '•', permission: fixedMachine.permission, menu: true, group: 'config', order: 3, view: 'shared', backup: true, fixed: true, hideIcon: !fixedMachine.icon, description: fixedMachine.description },
  { path: fixedMaterial.route, name: fixedMaterial.key, component: DomainModuleView, label: fixedMaterial.label, icon: fixedMaterial.icon || '•', permission: fixedMaterial.permission, menu: true, group: 'config', order: 4, view: 'shared', backup: true, fixed: true, hideIcon: !fixedMaterial.icon, description: fixedMaterial.description },
  { path: fixedMethod.route, name: fixedMethod.key, component: MethodDesign, label: fixedMethod.label, icon: fixedMethod.icon || '•', permission: fixedMethod.permission, menu: true, group: 'config', order: 5, view: 'shared', backup: true, fixed: true, hideIcon: !fixedMethod.icon, description: fixedMethod.description },
  { path: fixedEnvironment.route, name: fixedEnvironment.key, component: DomainModuleView, label: fixedEnvironment.label, icon: fixedEnvironment.icon || '•', permission: fixedEnvironment.permission, menu: true, group: 'config', order: 6, view: 'shared', backup: true, fixed: true, hideIcon: !fixedEnvironment.icon, description: fixedEnvironment.description },
]

export const MENU_ROUTES = APP_ROUTES.filter(r => r.menu)

export interface SearchTypeConfig {
  value: string
  label: string
  route: string
}

// 全局搜索类型也复用“路由 → 权限”绑定，避免菜单与搜索权限不一致。
export const SEARCH_TYPES: SearchTypeConfig[] = [
  { value: 'all', label: '全部', route: '' },
  { value: 'product', label: '产品', route: '/product-info' },
  { value: 'user', label: '人员', route: '/roles' },
  { value: 'station', label: '站点', route: '/station' },
  { value: 'wo', label: '工单', route: '/wo' },
  { value: 'sn', label: 'SN', route: '/query' },
  { value: 'box', label: '箱号', route: '/pack' },
]

export function searchTypeAllowed(t: SearchTypeConfig, permissions: string[]): boolean {
  if (!t.route) return true
  const perm = findAppRoute(t.route)?.permission || ''
  return !perm || permissions.includes(perm)
}

export function allowedSearchTypes(permissions: string[]): SearchTypeConfig[] {
  return SEARCH_TYPES.filter(t => searchTypeAllowed(t, permissions))
}

export function findAppRoute(path: string): AppRouteConfig | undefined {
  const exact = APP_ROUTES.find(r => r.path === path)
  if (exact) return exact
  const clean = String(path || '').split('?')[0].replace(/\/+$/, '')
  return APP_ROUTES.find((r) => {
    if (!r.path.includes(':')) return false
    const pattern = r.path
      .replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      .replace(/:[^/]+/g, '[^/]+')
    return new RegExp(`^${pattern}$`).test(clean)
  })
}

export function stationConfigFor(path: string): StationRouteConfig | undefined {
  return findAppRoute(path)?.station
}

export function routePathByPermission(permission: string): string {
  return APP_ROUTES.find(r => r.permission === permission)?.path || ''
}

export function isPublicRoute(path: string): boolean {
  return !!findAppRoute(path)?.public
}

export function firstAllowedPath(permissions: string[]): string {
  const menuPath = MENU_ROUTES.find(r => r.permission && permissions.includes(r.permission))?.path
  if (menuPath) return menuPath
  const backupPath = APP_ROUTES.find(r => r.backup && r.permission && permissions.includes(r.permission))?.path
  return backupPath || '/station'
}

export function validateRouteConfig(): void {
  const errors: string[] = []
  const seen = new Set<string>()
  const forbiddenRoleKeys = ['role', 'roleCode', 'role_code']
  APP_ROUTES.forEach((r, i) => {
    if (!r.path.startsWith('/')) errors.push(`第 ${i + 1} 项 path 必须以 / 开头：${r.path}`)
    if (seen.has(r.path)) errors.push(`重复 path：${r.path}`)
    seen.add(r.path)
    if (forbiddenRoleKeys.some(k => k in (r as any))) errors.push(`${r.path} 不应包含角色字段`)
    if (!r.component && !r.redirect) errors.push(`${r.path} 缺少 component 或 redirect`)
    if (r.component && r.redirect) errors.push(`${r.path} 不能同时配置 component 与 redirect`)
    if (!r.public && !r.redirect && !r.permission) errors.push(`${r.path} 是受保护路由，但未配置 permission`)
    if (r.menu) {
      if (!r.label) errors.push(`${r.path} 是菜单项，但未配置 label`)
      if (!r.icon) errors.push(`${r.path} 是菜单项，但未配置 icon`)
      if (!r.permission) errors.push(`${r.path} 是菜单项，但未配置 permission`)
      if (typeof r.order !== 'number') errors.push(`${r.path} 是菜单项，但未配置 order`)
      // 菜单项必须归属一个已定义的导航分组：分组写错会静默丢菜单，必须在启动时报出来
      if (!r.group) errors.push(`${r.path} 是菜单项，但未配置 group`)
      else if (!NAV_GROUPS.some(g => g.key === r.group)) errors.push(`${r.path} 的 group 未定义：${r.group}`)
    }
    if (r.parent) {
      if (r.parent === r.path) errors.push(`${r.path} 不能把自己设为 parent`)
      const parent = APP_ROUTES.find(item => item.path === r.parent)
      if (!parent) errors.push(`${r.path} 的 parent 指向不存在的路由：${r.parent}`)
      else if (!parent.menu) errors.push(`${r.path} 的 parent 不是菜单项：${r.parent}`)
    }
    if (r.station) {
      if (forbiddenRoleKeys.some(k => k in (r.station as any))) errors.push(`${r.path} 站点配置不应包含角色字段`)
      if (!r.station.flowStations?.length) errors.push(`${r.path} 站点配置缺少 flowStations`)
      if (!r.station.repairStation?.id) errors.push(`${r.path} 站点配置缺少维修站`)
    }
  })
  if (errors.length) {
    const message = '[route-config] 路由与菜单配置不一致：\n- ' + errors.join('\n- ')
    console.error(message)
    throw new Error(message)
  }
}

export function validateRoutePermissions(serverPermissions: string[]): string[] {
  const known = new Set(serverPermissions || [])
  return APP_ROUTES
    .filter(r => r.permission && !known.has(r.permission))
    .map(r => `${r.path} → ${r.permission}`)
}
