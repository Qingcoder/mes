export type AppIconKey =
  | 'wo' | 'query' | 'station' | 'pack'
  | 'access' | 'site' | 'role'
  | 'dashboard' | 'person' | 'machine' | 'material' | 'method' | 'environment'
  | 'search' | 'scan' | 'default'

export type AppIconSet = 'production' | 'system' | 'domain' | 'common'

export interface AppIconMeta {
  label: string
  glyph: string
  set: AppIconSet
}

export interface AppIconDefinition extends AppIconMeta {
  key: AppIconKey
  viewBox: string
  paths: string[]
}

export interface AppIconProps {
  name: string
  size?: number | string
  color?: string
  strokeWidth?: number
  label?: string
  decorative?: boolean
}
