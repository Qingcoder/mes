<template>
  <div class="login-card">
    <h2>账号登录</h2>
    <p class="device-tip">请使用系统分配的账号登录</p>
    <PasswordLoginForm
      v-model:username="username"
      v-model:password="password"
      :loading="loading"
      :error="msg"
      @submit="submit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, clearToken, setToken, setUser, setPermissions } from '../api'
import PasswordLoginForm from '../components/PasswordLoginForm.vue'

const router = useRouter()
const username = ref('admin')
const password = ref('')
const msg = ref('')
const loading = ref(false)
let finishing = false

async function finishLogin(payload: any) {
  if (finishing) return
  const token = String(payload?.token || '').trim()
  if (!token) {
    msg.value = '登录响应缺少有效令牌，请重新登录'
    return
  }
  finishing = true
  try {
    setToken(token)
    const u = {
      username: String(payload?.username || payload?.user?.username || username.value || ''),
      name: String(payload?.name || payload?.user?.name || '用户'),
      role: String(payload?.role || payload?.user?.role || ''),
      avatar: String(payload?.avatar || payload?.user?.avatar || ''),
    }
    setUser(u)
    let perms: string[] = []
    try {
      const me = await api.myPermissions()
      perms = me.permissions || []
      setUser({ username: me.username || u.username, name: me.name || u.name, role: me.role || u.role })
      setPermissions(perms)
    } catch (e: any) {
      clearToken()
      throw new Error(e?.message || '登录身份校验失败，请重新登录')
    }
    router.push('/')
  } finally {
    finishing = false
  }
}

async function submit() {
  if (loading.value) return
  loading.value = true; msg.value = ''
  clearToken()
  try {
    const r: any = await api.login(username.value.trim(), password.value)
    if (!r.ok) { msg.value = r.msg || '账号或密码错误'; return }
    await finishLogin(r)
  } catch (e: any) { msg.value = e.message || '登录失败，请稍后重试' }
  finally { loading.value = false }
}

</script>
