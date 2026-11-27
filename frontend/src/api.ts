// API 客户端 · 戴盟 MES 生产管理平台
const TOKEN_KEY = 'mes_token'
const USER_KEY = 'mes_user'
const PERM_KEY = 'mes_perms'
const PREVIEW_ROLE_KEY = 'mes_preview_role'

export type CurrentUser = { username: string; name: string; role: string; avatar?: string }

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t)
}
export function setUser(u: CurrentUser) {
  localStorage.setItem(USER_KEY, JSON.stringify(u))
}
export function getUser(): CurrentUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}
export function setPermissions(perms: string[]) {
  localStorage.setItem(PERM_KEY, JSON.stringify(perms || []))
}
export function getPermissions(): string[] {
  try { return JSON.parse(localStorage.getItem(PERM_KEY) || '[]') }
  catch { return [] }
}
export function setPreviewRole(role: string) {
  if (role) localStorage.setItem(PREVIEW_ROLE_KEY, role)
  else localStorage.removeItem(PREVIEW_ROLE_KEY)
}
export function getPreviewRole(): string {
  return localStorage.getItem(PREVIEW_ROLE_KEY) || ''
}
export function clearPreviewRole() {
  localStorage.removeItem(PREVIEW_ROLE_KEY)
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(PERM_KEY)
  localStorage.removeItem(PREVIEW_ROLE_KEY)
}

function requestHeaders(path: string, withContentType: boolean): Record<string, string> {
  const headers: Record<string, string> = {}
  if (withContentType) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) headers['Authorization'] = 'Bearer ' + token
  // 登录/扫码确认前可能残留上一次登录账号，认证接口不需要操作人头。
  if (!path.startsWith('/api/login') && !path.startsWith('/api/qr/')) {
    const operator = getUser()?.username
    if (operator) headers['X-Operator'] = encodeURIComponent(operator)
  }
  return headers
}

const FIELD_LABELS: Record<string, string> = {
  username: '用户名', password: '密码', name: '名称', code: '编码', role: '角色',
  title: '标题', value: '值', label: '标签', sn: 'SN', wo_no: '工单号',
  batch: '批次', status: '状态', count: '数量', file: '文件',
}
const ERROR_RULES: Array<[RegExp, string | ((match: RegExpExecArray) => string)]> = [
  [/field required/i, '此项为必填项'],
  [/string should have at least (\d+) characters?/i, (match: RegExpExecArray) => `内容至少需要 ${match[1]} 个字符`],
  [/string should have at most (\d+) characters?/i, (match: RegExpExecArray) => `内容不能超过 ${match[1]} 个字符`],
  [/input should be a valid/i, '输入格式不正确'],
  [/value error/i, '输入值不符合要求'],
  [/not found/i, '请求的数据不存在'],
  [/unauthorized/i, '登录状态失效，请重新登录'],
  [/forbidden/i, '当前账号没有权限执行此操作'],
  [/internal server error/i, '服务暂时不可用，请稍后重试'],
  [/timed? ?out|timeout/i, '请求超时，请稍后重试'],
  [/failed to execute 'fetch'|failed to fetch|networkerror|load failed|headers property/i, '无法连接服务，请检查网络或服务是否已启动'],
  [/unexpected end of json input|unexpected token/i, '服务返回的数据格式异常，请稍后重试'],
]

function translateText(raw: unknown, fallback = '操作失败，请稍后重试'): string {
  const text = String(raw || '').trim()
  if (!text) return fallback
  if (/[\u4e00-\u9fa5]/.test(text)) return text
  for (const [pattern, replacement] of ERROR_RULES) {
    const match = pattern.exec(text)
    if (match) return typeof replacement === 'function' ? replacement(match) : replacement
  }
  return fallback
}

function messageFromBody(body: any, fallback: string): string {
  const detail = body?.detail
  if (Array.isArray(detail)) {
    return detail.map((item: any) => {
      const loc = Array.isArray(item?.loc) ? item.loc.filter((x: any) => x !== 'body') : []
      const fieldKey = String(loc[loc.length - 1] || '')
      const field = FIELD_LABELS[fieldKey] || fieldKey
      const text = translateText(item?.msg, '参数不合法')
      return field ? `${field}：${text}` : text
    }).join('；')
  }
  return translateText(detail || body?.msg, fallback)
}

function statusMessage(status: number): string {
  if (status === 400) return '请求参数不正确'
  if (status === 401) return '登录状态失效，请重新登录'
  if (status === 403) return '当前账号没有权限执行此操作'
  if (status === 404) return '请求的数据不存在'
  if (status === 405) return '请求方式不被支持'
  if (status >= 500) return '服务暂时不可用，请稍后重试'
  return `请求失败（${status}）`
}

function fetchErrorMessage(error: unknown, action = '请求'): Error {
  const raw = error instanceof Error ? error.message : String(error || '')
  return new Error(translateText(raw, `${action}失败，请稍后重试`))
}

export function friendlyError(error: unknown, fallback = '操作失败，请稍后重试'): string {
  const raw = error instanceof Error ? error.message : String(error || '')
  return translateText(raw, fallback)
}

function uploadWithProgress<T = any>(path: string, form: FormData, onProgress?: (loaded: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', path)
    Object.entries(requestHeaders(path, false)).forEach(([key, value]) => xhr.setRequestHeader(key, value))
    if (onProgress) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded)
      }
    }
    xhr.onload = () => {
      let body: any = {}
      try { body = JSON.parse(xhr.responseText || '{}') } catch { body = {} }
      if (xhr.status < 200 || xhr.status >= 300) {
        handleUnauthorized(path, xhr.status)
        reject(new Error(messageFromBody(body, statusMessage(xhr.status))))
        return
      }
      resolve(body as T)
    }
    xhr.onerror = () => reject(new Error('网络连接中断，可点击重试继续上传'))
    xhr.onabort = () => reject(new Error('上传已取消'))
    xhr.send(form)
  })
}

async function parseBody(res: Response): Promise<any> {
  const text = await res.text()
  if (!text) return {}
  try { return JSON.parse(text) } catch { return {} }
}

function handleUnauthorized(path: string, status: number) {
  if (status !== 401 || path.startsWith('/api/login') || path.startsWith('/api/qr/')) return
  clearToken()
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('mes-unauthorized'))
}

async function reqForm<T = any>(path: string, form: FormData): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { method: 'POST', headers: requestHeaders(path, false), body: form })
  } catch (e) { throw fetchErrorMessage(e, '上传') }
  const body = await parseBody(res)
  if (!res.ok) {
    handleUnauthorized(path, res.status)
    throw new Error(messageFromBody(body, statusMessage(res.status)))
  }
  return body as T
}

async function reqBlob(path: string): Promise<Blob> {
  let res: Response
  try {
    res = await fetch(path, { headers: requestHeaders(path, false) })
  } catch (e) { throw fetchErrorMessage(e, '下载') }
  if (!res.ok) {
    handleUnauthorized(path, res.status)
    const body = await parseBody(res)
    throw new Error(messageFromBody(body, statusMessage(res.status)))
  }
  return res.blob()
}

async function req<T = any>(path: string, data?: any, method?: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      method: method || (data !== undefined ? 'POST' : 'GET'),
      headers: requestHeaders(path, true),
      body: data !== undefined ? JSON.stringify(data) : undefined,
    })
  } catch (e) { throw fetchErrorMessage(e) }
  const body = await parseBody(res)
  if (!res.ok) {
    handleUnauthorized(path, res.status)
    throw new Error(messageFromBody(body, statusMessage(res.status)))
  }
  return body as T
}

export const api = {
  login: (username: string, password: string) => req('/api/login', { username, password }),
  accountProfile: () => req<any>('/api/account/profile'),
  updateAccountProfile: (payload: any) => req<any>('/api/account/profile', payload, 'PUT'),
  changeAccountPassword: (currentPassword: string, newPassword: string) =>
    req<any>('/api/account/password', { currentPassword, newPassword }, 'POST'),
  qrCreate: () => req<{ sid: string; ttl: number }>('/api/qr/create', {}),
  lanInfo: () => req<{ ips: string[]; loginUrls: string[]; recommended: string }>('/api/lan-info'),
  qrStatus: (sid: string) => req<{ status: string; user?: CurrentUser & { token?: string } }>(`/api/qr/status?sid=${encodeURIComponent(sid)}`),
  qrConfirm: (sid: string) => req(`/api/qr/confirm?sid=${encodeURIComponent(sid)}`, {}),
  products: () => req<any[]>('/api/products'),
  productProfiles: () => req<any[]>('/api/product-profiles'),
  productProfile: (code: string) => req<any>(`/api/product-profiles/${encodeURIComponent(code)}`),
  lookupProductSn: (sn: string) => req<any>(`/api/product-profiles/lookup?sn=${encodeURIComponent(sn)}`),
  createSimpleProduct: (name: string) => req<any>('/api/product-profiles/simple', { name }, 'POST'),
  renameProductName: (code: string, name: string) => req<any>(`/api/product-profiles/${encodeURIComponent(code)}/name`, { name }, 'PUT'),
  importProductSns: (code: string, sns: string[]) => req<any>(`/api/product-profiles/${encodeURIComponent(code)}/sns/import`, { sns }, 'POST'),
  createProductProfile: (payload: any) => req<any>('/api/product-profiles', payload, 'POST'),
  createProductProfilesBatch: (payload: any) => req<any>('/api/product-profiles/batch', payload, 'POST'),
  updateProductProfile: (code: string, payload: any) => req<any>(`/api/product-profiles/${encodeURIComponent(code)}`, payload, 'PUT'),
  deleteProductProfile: (code: string) => req<any>(`/api/product-profiles/${encodeURIComponent(code)}`, undefined, 'DELETE'),
  addProductSns: (code: string, payload: any) => req<any>(`/api/product-profiles/${encodeURIComponent(code)}/sns`, payload, 'POST'),
  updateProductSn: (code: string, sn: string, payload: any) => req<any>(`/api/product-profiles/${encodeURIComponent(code)}/sns/${encodeURIComponent(sn)}`, payload, 'PUT'),
  deleteProductSn: (code: string, sn: string) => req<any>(`/api/product-profiles/${encodeURIComponent(code)}/sns/${encodeURIComponent(sn)}`, undefined, 'DELETE'),
  deleteProductSns: (code: string, sns: string[]) => req<any>(`/api/product-profiles/${encodeURIComponent(code)}/sns/delete`, { sns }, 'POST'),
  snLibrarySummary: () => req<any>('/api/sn-library/summary'),
  snLibraryRecords: (filters: Record<string, string> = {}) => {
    const p = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => { if (v) p.set(k, v) })
    const query = p.toString()
    return req<any[]>(`/api/sn-library${query ? '?' + query : ''}`)
  },
  snLibraryDetail: (id: string) => req<any>(`/api/sn-library/${encodeURIComponent(id)}`),
  createSnLibrary: (payload: any) => req<any>('/api/sn-library', payload, 'POST'),
  updateSnLibrary: (id: string, payload: any) => req<any>(`/api/sn-library/${encodeURIComponent(id)}`, payload, 'PUT'),
  deleteSnLibrary: (id: string) => req<any>(`/api/sn-library/${encodeURIComponent(id)}`, undefined, 'DELETE'),
  listWO: () => req<any[]>('/api/wos'),
  woFlowOptions: () => req<any>('/api/wos/flow-options'),
  nextWoNo: () => req<{ wo_no: string }>('/api/wos/next-no'),
  relationOptions: () => req<any>('/api/relation-options'),
  createWO: (d: any) => req('/api/wos', d),
  getWO: (id: number) => req(`/api/wos/${id}`),
  importSN: (woId: number, sns: string[]) => req(`/api/wos/${woId}/sns`, { wo_id: woId, sns }),
  station: (d: any) => req('/api/station', d),
  replaceSn: (d: any) => req('/api/station/replace-sn', d, 'POST'),
  rework: (woId: number, sn: string) => req(`/api/wos/${woId}/sns/${encodeURIComponent(sn)}/rework`, {}),
  pack: (d: any) => req('/api/pack', d),
  querySN: (sn: string) => req(`/api/query/sn/${encodeURIComponent(sn)}`),
  queryWO: (id: number) => req(`/api/query/wo/${id}`),
  queryBox: (no: string) => req(`/api/query/box/${encodeURIComponent(no)}`),
  unifiedConfig: () => req('/api/unified/config'),
  unifiedHealth: () => req('/api/unified/health'),
  unifiedListWO: () => req<any[]>('/api/unified/wos'),
  unifiedGetWO: (id: number) => req(`/api/unified/wos/${id}`),
  unifiedQueryWO: (id: number) => req(`/api/unified/query/wo/${id}`),
  unifiedStation: (d: any, route = '/station') => req(`/api/unified/station?route=${encodeURIComponent(route)}`, d),
  unifiedAssign: (route = '/station') => req<any>(`/api/unified/assign?route=${encodeURIComponent(route)}`),
  unifiedResolveSn: (sn: string, route = '/station') => req<any>(`/api/unified/resolve-sn?route=${encodeURIComponent(route)}`, { sn }),
  unifiedQuerySn: (sn: string, source = '') => req<any>(`/api/unified/query/sn/${encodeURIComponent(sn)}?source=${encodeURIComponent(source)}`),
  unifiedStationContext: (route = '/station') => req<any>(`/api/unified/station-context?route=${encodeURIComponent(route)}`),
  permissions: () => req<any[]>('/api/permissions'),
  roles: (keyword = '') => req<any[]>(`/api/roles?keyword=${encodeURIComponent(keyword)}`),
  nextRoleCode: () => req<{ code: string }>('/api/roles/next-code'),
  myPermissions: () => req<{ username: string; name: string; role: string; permissions: string[] }>('/api/me/permissions'),
  createAccount: (d: any) => req('/api/accounts', d),
  permissionMap: () => req<any>('/api/permission-map'),
  permissionTable: () => req<any>('/api/permission-table'),
  permissionAudit: (limit = 50, days?: number) => req<any[]>(`/api/permission-audit?limit=${limit}${days ? `&days=${days}` : ''}`),
  cleanupAudit: (days = 90) => req(`/api/permission-audit?days=${days}`, undefined, 'DELETE'),
  globalSearch: (q: string, type = 'all') => req<any>(`/api/search?q=${encodeURIComponent(q)}&type=${encodeURIComponent(type)}`),
  snLogs: (q: Record<string, any>) => {
    const p = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, String(v)) })
    return req(`/api/sn-logs?${p.toString()}`)
  },
  createRole: (d: any) => req('/api/roles', d),
  updateRole: (code: string, d: any) => req(`/api/roles/${encodeURIComponent(code)}`, d, 'PUT'),
  deleteRole: (code: string) => req(`/api/roles/${encodeURIComponent(code)}`, undefined, 'DELETE'),
  restoreRole: (code: string) => req(`/api/roles/${encodeURIComponent(code)}/restore`, {}, 'POST'),
  rolePerms: (code: string) => req<string[]>(`/api/roles/${encodeURIComponent(code)}/permissions`),
  setRolePerms: (code: string, permissions: string[]) => req(`/api/roles/${encodeURIComponent(code)}/permissions`, { permissions }, 'PUT'),
  accessOptions: () => req<any>('/api/access/options'),
  accessGrants: () => req<any>('/api/access/grants'),
  createAccessGrant: (d: any) => req('/api/access/grants', d),
  updateAccessGrant: (id: string, d: any) => req(`/api/access/grants/${encodeURIComponent(id)}`, d, 'PUT'),
  deleteAccessGrant: (id: string) => req(`/api/access/grants/${encodeURIComponent(id)}`, undefined, 'DELETE'),
  checkAccess: (scopeType: string, scopeValue: string, action = 'view') =>
    req<any>(`/api/access/check?scopeType=${encodeURIComponent(scopeType)}&scopeValue=${encodeURIComponent(scopeValue)}&action=${encodeURIComponent(action)}`),
  customSites: () => req<any>('/api/custom-sites'),
  createCustomSite: (d: any) => req('/api/custom-sites/sites', d),
  updateCustomSite: (id: string, d: any) => req(`/api/custom-sites/sites/${encodeURIComponent(id)}`, d, 'PUT'),
  deleteCustomSite: (id: string) => req(`/api/custom-sites/sites/${encodeURIComponent(id)}`, undefined, 'DELETE'),
  createSiteGroup: (d: any) => req('/api/custom-sites/groups', d),
  updateSiteGroup: (id: string, d: any) => req(`/api/custom-sites/groups/${encodeURIComponent(id)}`, d, 'PUT'),
  deleteSiteGroup: (id: string) => req(`/api/custom-sites/groups/${encodeURIComponent(id)}`, undefined, 'DELETE'),
  createSiteFlow: (d: any) => req('/api/custom-sites/flows', d),
  updateSiteFlow: (id: string, d: any) => req(`/api/custom-sites/flows/${encodeURIComponent(id)}`, d, 'PUT'),
  deleteSiteFlow: (id: string) => req(`/api/custom-sites/flows/${encodeURIComponent(id)}`, undefined, 'DELETE'),
  nextCustomSite: (siteId: string) => req<any>(`/api/custom-sites/next?siteId=${encodeURIComponent(siteId)}`),
  domainConfig: () => req<any>('/api/domain-config'),
  saveDomainConfig: (domains: any[]) => req<any>('/api/domain-config', { domains }, 'PUT'),
  persons: () => req<any>('/api/persons'),
  personOptions: () => req<any>('/api/persons/options'),
  createPerson: (d: any) => req<any>('/api/persons', d),
  updatePerson: (username: string, d: any) => req<any>(`/api/persons/${encodeURIComponent(username)}`, d, 'PUT'),
  setPersonRole: (username: string, role: string) => req<any>(`/api/persons/${encodeURIComponent(username)}/role`, { role }, 'PUT'),
  renamePersonPosition: (oldPosition: string, newPosition: string) => req<any>('/api/persons/position/rename', { oldPosition, newPosition }, 'PUT'),
  personPermissions: (username: string) => req<any>(`/api/persons/${encodeURIComponent(username)}/permissions`),
  setPersonPermissions: (username: string, permissions: string[]) => req<any>(`/api/persons/${encodeURIComponent(username)}/permissions`, { permissions }, 'PUT'),
  personScope: (username: string) => req<any>(`/api/persons/${encodeURIComponent(username)}/scope`),
  functionTree: () => req<any>('/api/function-tree'),
  functionRoutes: () => req<any>('/api/function-tree/routes'),
  roleTemplates: () => req<any>('/api/function-tree/templates'),
  moduleRegistry: () => req<any>('/api/function-tree/module-registry'),
  processDesign: () => req<any>('/api/process-design'),
  processDesignOptions: () => req<any>('/api/process-design/options'),
  saveProcessDesign: (config: any) => req<any>('/api/process-design', { config }, 'PUT'),
  processDesignMaster: () => req<any>('/api/process-design/master'),
  defectCodes: (filters: Record<string, string> = {}) => {
    const p = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => { if (v) p.set(k, v) })
    return req<any[]>(`/api/defect-codes${p.toString() ? `?${p.toString()}` : ''}`)
  },
  defectCodeOptions: () => req<any>('/api/defect-codes/options'),
  defectCodeTemplate: () => reqBlob('/api/defect-codes/template'),
  createDefectCode: (d: any) => req<any>('/api/defect-codes', d, 'POST'),
  updateDefectCode: (code: string, d: any) => req<any>(`/api/defect-codes/${encodeURIComponent(code)}`, d, 'PUT'),
  deleteDefectCode: (code: string) => req<any>(`/api/defect-codes/${encodeURIComponent(code)}`, undefined, 'DELETE'),
  importDefectCodes: (rows: any[]) => req<any>('/api/defect-codes/import', { rows }, 'POST'),
  saveProcessDesignMaster: (patch: any) => req<any>('/api/process-design/master', patch, 'PUT'),
  qualityDashboard: () => req<any>('/api/quality-dashboard/summary'),
  environmentOverview: () => req<any>('/api/environment/overview'),
  environmentOptions: () => req<any>('/api/environment/options'),
  environmentResources: (filters: Record<string, string> = {}) => {
    const p = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => { if (v) p.set(k, v) })
    const query = p.toString()
    return req<any[]>(`/api/environment/resources${query ? '?' + query : ''}`)
  },
  uploadEnvironmentResource: (form: FormData) => reqForm<any>('/api/environment/resources', form),
  updateEnvironmentResource: (id: string, payload: any) => req<any>(`/api/environment/resources/${encodeURIComponent(id)}`, payload, 'PUT'),
  deleteEnvironmentResource: (id: string) => req<any>(`/api/environment/resources/${encodeURIComponent(id)}`, undefined, 'DELETE'),
  downloadEnvironmentResource: (id: string) => reqBlob(`/api/environment/resources/${encodeURIComponent(id)}/download`),
  createUploadSession: (payload: any) => req<any>('/api/process-design/upload-sessions', payload, 'POST'),
  uploadSessionStatus: (sessionId: string) => req<any>(`/api/process-design/upload-sessions/${encodeURIComponent(sessionId)}`),
  uploadChunk: (sessionId: string, index: number, blob: Blob, onProgress?: (loaded: number) => void) => {
    const form = new FormData()
    form.append('chunk', blob, `chunk-${index}.part`)
    return uploadWithProgress<any>(`/api/process-design/upload-sessions/${encodeURIComponent(sessionId)}/chunks/${index}`, form, onProgress)
  },
  completeUploadSession: (sessionId: string) => req<any>(`/api/process-design/upload-sessions/${encodeURIComponent(sessionId)}/complete`, {}, 'POST'),
  cancelUploadSession: (sessionId: string) => req<any>(`/api/process-design/upload-sessions/${encodeURIComponent(sessionId)}`, undefined, 'DELETE'),
  uploadParamFile: (stationId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return reqForm<any>(`/api/process-design/parameter-files?station_id=${encodeURIComponent(stationId)}`, form)
  },
  downloadParamFile: (stationId: string, fileId: string) => reqBlob(`/api/process-design/parameter-files/${encodeURIComponent(stationId)}/${encodeURIComponent(fileId)}`),
  deleteParamFile: (stationId: string, fileId: string) => req<any>(`/api/process-design/parameter-files/${encodeURIComponent(stationId)}/${encodeURIComponent(fileId)}`, undefined, 'DELETE'),
  createRoleCombination: (d: any) => req<any>('/api/role-combinations', d),
  equipmentSummary: () => req<any>('/api/equipment/summary'),
  equipmentOptions: () => req<any>('/api/equipment/options'),
  equipmentList: (filters: Record<string, string> = {}) => {
    const p = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => { if (v) p.set(k, v) })
    const query = p.toString()
    return req<any[]>(`/api/equipment${query ? '?' + query : ''}`)
  },
  equipmentDetail: (code: string) => req<any>(`/api/equipment/${encodeURIComponent(code)}`),
  createEquipment: (payload: any) => req<any>('/api/equipment', payload, 'POST'),
  updateEquipment: (code: string, payload: any) => req<any>(`/api/equipment/${encodeURIComponent(code)}`, payload, 'PUT'),
  deleteEquipment: (code: string) => req<any>(`/api/equipment/${encodeURIComponent(code)}`, undefined, 'DELETE'),
  importEquipment: (rows: any[]) => req<any>('/api/equipment/import', { rows }, 'POST'),
  addEquipmentMaintenance: (code: string, payload: any) => req<any>(`/api/equipment/${encodeURIComponent(code)}/maintenance`, payload, 'POST'),
  updateEquipmentMaintenance: (code: string, recordId: string, payload: any) => req<any>(`/api/equipment/${encodeURIComponent(code)}/maintenance/${encodeURIComponent(recordId)}`, payload, 'PUT'),
  deleteEquipmentMaintenance: (code: string, recordId: string) => req<any>(`/api/equipment/${encodeURIComponent(code)}/maintenance/${encodeURIComponent(recordId)}`, undefined, 'DELETE'),
  moduleSkeletonModules: () => req<any>('/api/module-skeleton/modules'),
  moduleSkeletonMeta: (key: string) => req<any>(`/api/module-skeleton/${encodeURIComponent(key)}/meta`),
  moduleSkeletonRecords: (key: string) => req<any>(`/api/module-skeleton/${encodeURIComponent(key)}/records`),
  createModuleSkeletonRecord: (key: string, data: any) => req<any>(`/api/module-skeleton/${encodeURIComponent(key)}/records`, { data }),
  updateModuleSkeletonRecord: (key: string, id: string, data: any) => req<any>(`/api/module-skeleton/${encodeURIComponent(key)}/records/${encodeURIComponent(id)}`, { data }, 'PUT'),
  deleteModuleSkeletonRecord: (key: string, id: string) => req<any>(`/api/module-skeleton/${encodeURIComponent(key)}/records/${encodeURIComponent(id)}`, undefined, 'DELETE'),
}

export const globalSearch = (q: string, type = 'all') => api.globalSearch(q, type)
