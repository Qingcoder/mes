import { computed, ref } from 'vue'
import { api, friendlyError } from '../api'

/** 产品主数据共享逻辑：物料域「产品主数据」面板与「产品资料」页共用同一套增删改查。 */
export function useProductProfiles() {
  const profiles = ref<any[]>([])
  const loading = ref(false)
  const error = ref('')
  const notice = ref('')

  async function load(): Promise<any[]> {
    loading.value = true
    error.value = ''
    try {
      profiles.value = await api.productProfiles()
      return profiles.value
    } catch (e: any) {
      error.value = friendlyError(e, '产品列表加载失败')
      return profiles.value
    } finally {
      loading.value = false
    }
  }

  async function create(name: string): Promise<any | null> {
    const value = String(name || '').trim()
    if (!value) { error.value = '请输入产品名称'; return null }
    error.value = ''
    try {
      const created = await api.createSimpleProduct(value)
      notice.value = `产品已创建：${created.code}`
      await load()
      return created
    } catch (e: any) {
      error.value = friendlyError(e, '产品创建失败')
      return null
    }
  }

  async function rename(code: string, name: string): Promise<boolean> {
    const value = String(name || '').trim()
    if (!code) return false
    if (!value) { error.value = '产品名称不能为空'; return false }
    error.value = ''
    try {
      await api.renameProductName(code, value)
      notice.value = '产品名称已保存'
      await load()
      return true
    } catch (e: any) {
      error.value = friendlyError(e, '产品名称保存失败')
      return false
    }
  }

  async function remove(code: string): Promise<boolean> {
    if (!code) return false
    error.value = ''
    try {
      await api.deleteProductProfile(code)
      notice.value = '产品已删除'
      await load()
      return true
    } catch (e: any) {
      error.value = friendlyError(e, '产品删除失败')
      return false
    }
  }

  /** 按关键字过滤产品列表（编码或名称）。 */
  function filterRows(keyword: string): any[] {
    const q = String(keyword || '').trim().toLowerCase()
    if (!q) return profiles.value
    return profiles.value.filter(row => `${row.code} ${row.name}`.toLowerCase().includes(q))
  }

  const total = computed(() => profiles.value.length)

  return { profiles, loading, error, notice, total, load, create, rename, remove, filterRows }
}
