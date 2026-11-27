import { ref } from 'vue'
import { api } from '../api'

export function usePersonnel() {
  const persons = ref<any[]>([])
  const options = ref<any[]>([])
  const loading = ref(false)
  const error = ref('')

  async function loadPersons() {
    loading.value = true; error.value = ''
    try {
      const data: any = await api.persons()
      persons.value = data.items || []
    } catch (e: any) {
      error.value = e.message || '人员列表加载失败'
    } finally {
      loading.value = false
    }
  }

  async function loadOptions() {
    try {
      const data: any = await api.personOptions()
      options.value = data.items || []
    } catch { options.value = [] }
  }

  return { persons, options, loading, error, loadPersons, loadOptions }
}
