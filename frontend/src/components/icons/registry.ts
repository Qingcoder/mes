import type { AppIconDefinition, AppIconKey, AppIconMeta, AppIconSet } from './types'

const META: Record<AppIconKey, AppIconMeta> = {
  wo: { label: '工单管理', glyph: '▤', set: 'production' },
  query: { label: '数据查询', glyph: '⌕', set: 'production' },
  station: { label: '站点作业', glyph: '▷', set: 'production' },
  pack: { label: '包装管理', glyph: '▣', set: 'production' },
  access: { label: '站点流程权限', glyph: '⚿', set: 'system' },
  site: { label: '自定义站点', glyph: '◇', set: 'system' },
  role: { label: '权限管理', glyph: '◈', set: 'system' },
  dashboard: { label: '看板', glyph: '▦', set: 'domain' },
  person: { label: '人员管理', glyph: '◉', set: 'domain' },
  machine: { label: '设备管理', glyph: '⚙', set: 'domain' },
  material: { label: '物料管理', glyph: '▦', set: 'domain' },
  method: { label: '工艺管理', glyph: '⇉', set: 'domain' },
  environment: { label: '环境配置', glyph: '◎', set: 'domain' },
  search: { label: '全局搜索', glyph: '⌕', set: 'system' },
  scan: { label: '应用内扫码', glyph: '⌖', set: 'system' },
  default: { label: '功能模块', glyph: '•', set: 'common' },
  check: { label: '通过', glyph: '✓', set: 'station' },
  circleCheck: { label: '已完成', glyph: '✓', set: 'station' },
  clock: { label: '待过站', glyph: '◷', set: 'station' },
  wrench: { label: '维修站', glyph: '⚒', set: 'station' },
  lock: { label: '锁定', glyph: '⚿', set: 'station' },
  building: { label: '不良上报', glyph: '⌂', set: 'station' },
  alert: { label: '警告', glyph: '⚠', set: 'station' },
  chevronRight: { label: '进入', glyph: '›', set: 'station' },
  clipboard: { label: '工单', glyph: '▤', set: 'station' },
  operator: { label: '操作员', glyph: '◉', set: 'station' },
  barcode: { label: '扫码输入', glyph: '⌗', set: 'station' },
}

const LOADERS: Record<AppIconSet, () => Promise<{ default: Record<string, string[]> }>> = {
  production: () => import('./sets/production'),
  system: () => import('./sets/system'),
  domain: () => import('./sets/domain'),
  common: () => import('./sets/common'),
  station: () => import('./sets/station'),
}

const cache = new Map<AppIconSet, Promise<Record<string, string[]>>>()

function loadSet(set: AppIconSet): Promise<Record<string, string[]>> {
  if (!cache.has(set)) cache.set(set, LOADERS[set]().then(m => m.default))
  return cache.get(set)!
}

export function hasIcon(key: unknown): key is AppIconKey {
  return typeof key === 'string' && key in META
}

export function iconMeta(key: string): AppIconMeta {
  return hasIcon(key) ? META[key] : META.default
}

export function appIcon(key: string): { glyph: string; label: string } {
  const meta = iconMeta(key)
  return { glyph: meta.glyph, label: meta.label }
}

export async function loadIcon(key: string): Promise<AppIconDefinition> {
  const safeKey = hasIcon(key) ? key : 'default'
  const meta = META[safeKey]
  const setPaths = await loadSet(meta.set)
  let paths = setPaths[safeKey]
  if (!Array.isArray(paths) && safeKey !== 'default') {
    paths = (await loadSet('common')).default
  }
  return {
    key: safeKey,
    label: meta.label,
    glyph: meta.glyph,
    set: meta.set,
    viewBox: '0 0 24 24',
    paths: Array.isArray(paths) ? paths : [],
  }
}

export const APP_ICON_KEYS = Object.keys(META) as AppIconKey[]
