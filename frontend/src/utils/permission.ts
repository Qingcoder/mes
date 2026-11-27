export const PERM = {
  WO_VIEW: 'wo:view',
  WO_CREATE: 'wo:create',
  SN_IMPORT: 'sn:import',
  STATION_OP: 'station:op',
  REWORK_OP: 'rework:op',
  PACK_OP: 'pack:op',
  QUERY_VIEW: 'query:view',
  USER_MANAGE: 'system:user:manage',
  ROLE_MANAGE: 'system:role:manage',
  ACCESS_MANAGE: 'system:access:manage',
} as const

export type RoleView = 'admin' | 'operator' | 'user'
export type RouteView = RoleView | 'shared'

export const ROLE_VIEW_LABEL: Record<RoleView, string> = {
  admin: '管理员',
  operator: '作业员',
  user: '普通用户',
}

const ADMIN_PERMS = [PERM.ROLE_MANAGE, PERM.USER_MANAGE, PERM.ACCESS_MANAGE]
const OPERATOR_EXCLUDE = [
  PERM.WO_VIEW, PERM.WO_CREATE, PERM.SN_IMPORT, PERM.REWORK_OP,
  PERM.PACK_OP, PERM.QUERY_VIEW, ...ADMIN_PERMS,
]

export function hasPerm(permissions: string[], permission: string): boolean {
  return Array.isArray(permissions) && permissions.includes(permission)
}

export function hasAnyPerm(permissions: string[], list: string[]): boolean {
  return Array.isArray(permissions) && list.some(p => permissions.includes(p))
}

export function isAdminPerms(permissions: string[]): boolean {
  return hasAnyPerm(permissions, ADMIN_PERMS)
}

export function canManageAccess(permissions: string[]): boolean {
  return hasAnyPerm(permissions, [PERM.ACCESS_MANAGE, PERM.ROLE_MANAGE])
}

export function roleViewOf(roleCode: string, permissions: string[]): RoleView {
  if (roleCode === 'admin' || isAdminPerms(permissions)) return 'admin'
  if (hasPerm(permissions, PERM.STATION_OP) && !hasAnyPerm(permissions, OPERATOR_EXCLUDE)) return 'operator'
  return 'user'
}

export function routeAllowsView(routeView: RouteView | undefined, roleView: RoleView): boolean {
  if (!routeView || routeView === 'shared') return true
  if (roleView === 'admin') return true
  return routeView === roleView
}

export function defaultPathFor(_roleView: RoleView, _permissions: string[], firstAllowedPath: string): string {
  return firstAllowedPath || '/station'
}
