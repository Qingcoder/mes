export type AuthMode = 'pwd' | 'qr'

export interface AuthTab {
  value: AuthMode
  label: string
}

export const DEFAULT_AUTH_TABS: AuthTab[] = [
  { value: 'pwd', label: '账号登录' },
  { value: 'qr', label: '扫码登录' },
]
