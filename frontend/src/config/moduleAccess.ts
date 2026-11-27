export interface ModuleAccessItem {
  path: string
  label: string
  permission: string
  group: string
}

// 用于人员模块的“可访问路由预览”。路由注册仍以 routeConfig.ts 为准。
export const MODULE_ACCESS_ITEMS: ModuleAccessItem[] = [
  { path: '/wo', label: '工单管理', permission: 'wo:view', group: '生产管理' },
  { path: '/station', label: '站点作业', permission: 'station:op', group: '生产作业' },
  { path: '/sn-detail', label: 'SN 详情', permission: 'station:op', group: '生产作业' },
  { path: '/pack', label: '包装管理', permission: 'pack:op', group: '生产作业' },
  { path: '/query', label: '数据追溯', permission: 'query:view', group: '生产管理' },
  { path: '/access-control', label: '站点流程权限', permission: 'system:access:manage', group: '系统管理' },
  { path: '/site-manage', label: '自定义站点', permission: 'system:access:manage', group: '系统管理' },
  { path: '/roles', label: '权限管理', permission: 'system:role:manage', group: '系统管理' },
  { path: '/dashboard', label: '看板', permission: 'dashboard:view', group: '核心模块' },
  { path: '/person', label: '人员管理', permission: 'person:manage', group: '核心模块' },
  { path: '/machine', label: '设备管理', permission: 'machine:manage', group: '核心模块' },
  { path: '/material', label: '物料管理', permission: 'material:manage', group: '核心模块' },
  { path: '/method', label: '工艺管理', permission: 'method:manage', group: '核心模块' },
  { path: '/environment', label: '环境配置', permission: 'environment:manage', group: '核心模块' },
]

export function routesForPermissions(permissions: string[]): ModuleAccessItem[] {
  const set = new Set(permissions || [])
  return MODULE_ACCESS_ITEMS.filter(item => set.has(item.permission))
}
