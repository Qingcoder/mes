import { ref } from 'vue'
import { getPermissions } from '../api'

// 全局共享的响应式权限：App.vue 切换角色时更新，Station.vue 等页面实时读取。
export const sharedPerms = ref<string[]>(getPermissions())

export function setSharedPerms(perms: string[]) {
  sharedPerms.value = Array.isArray(perms) ? perms.slice() : []
}
