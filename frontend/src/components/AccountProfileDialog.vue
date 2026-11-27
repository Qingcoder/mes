<template>
  <div v-if="open" class="modal-mask" @click.self="close">
    <div class="modal" role="dialog" aria-modal="true">
      <div class="panel-head">
        <div>
          <b>个人资料与密码</b>
          <p class="sub">仅维护当前登录账号；登录用户名和角色由系统管理维护。</p>
        </div>
        <button class="btn sm" type="button" @click="close">关闭</button>
      </div>

      <div v-if="error" class="msg err">{{ error }}</div>
      <div v-if="notice" class="msg ok">{{ notice }}</div>

      <div v-if="loading" class="empty">加载账号信息…</div>
      <template v-else>
        <form @submit.prevent>
        <h4>基本资料</h4>
        <div class="form-grid">
          <label>登录用户名<input :value="profile.username" disabled /></label>
          <label>角色<input :value="roleLabel" disabled /></label>
          <label>姓名<input v-model="profile.name" maxlength="64" /></label>
          <label>头像标识<input v-model="profile.avatar" maxlength="4" placeholder="留空则取姓名首字" /></label>
        </div>
        <div class="actions">
          <button class="btn primary" type="button" :disabled="saving" @click="saveProfile">保存资料</button>
        </div>

        <h4>修改密码</h4>
        <div class="form-grid">
          <label>当前密码<input v-model="password.current" type="password" autocomplete="current-password" /></label>
          <label>新密码<input v-model="password.next" type="password" autocomplete="new-password" placeholder="至少 6 位" /></label>
          <label>确认新密码<input v-model="password.confirm" type="password" autocomplete="new-password" /></label>
        </div>
        <div class="actions">
          <button class="btn primary" type="button" :disabled="saving" @click="changePassword">修改密码</button>
        </div>
        </form>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { api, setUser } from '../api'

const props = defineProps<{ open: boolean; user: any; roleLabel: string }>()
const emit = defineEmits<{ (event: 'close'): void; (event: 'updated'): void }>()

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const profile = reactive<any>({ username: '', name: '', role: '', avatar: '' })
const password = reactive({ current: '', next: '', confirm: '' })

watch(() => props.open, async (open) => {
  if (!open) return
  error.value = ''
  notice.value = ''
  password.current = ''
  password.next = ''
  password.confirm = ''
  loading.value = true
  try {
    const data: any = await api.accountProfile()
    Object.assign(profile, data)
  } catch (e: any) {
    error.value = e.message || '账号信息加载失败'
  } finally {
    loading.value = false
  }
})

function close() { emit('close') }
function clearMessages() { error.value = ''; notice.value = '' }

async function saveProfile() {
  clearMessages()
  if (!String(profile.name || '').trim()) { error.value = '姓名不能为空'; return }
  saving.value = true
  try {
    const data: any = await api.updateAccountProfile({ name: profile.name, avatar: profile.avatar })
    Object.assign(profile, data)
    setUser({ username: data.username, name: data.name, role: data.role, avatar: data.avatar })
    notice.value = '个人资料已保存'
    emit('updated')
  } catch (e: any) {
    error.value = e.message || '个人资料保存失败'
  } finally {
    saving.value = false
  }
}

async function changePassword() {
  clearMessages()
  if (!password.current) { error.value = '请输入当前密码'; return }
  if (password.next.length < 6) { error.value = '新密码至少 6 位'; return }
  if (password.next !== password.confirm) { error.value = '两次输入的新密码不一致'; return }
  saving.value = true
  try {
    const data: any = await api.changeAccountPassword(password.current, password.next)
    password.current = ''
    password.next = ''
    password.confirm = ''
    notice.value = data?.message || '密码已修改'
  } catch (e: any) {
    error.value = e.message || '密码修改失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-mask { position: fixed; inset: 0; z-index: 200; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(4,8,18,.65); }
.modal { width: 100%; max-width: 640px; max-height: 92dvh; overflow: auto; background: var(--white); border-radius: 10px; padding: 18px; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
h4 { font-size: 14px; margin: 18px 0 8px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; }
.form-grid label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
input { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 8px; font-family: inherit; color: var(--ink); background: var(--white); }
input:disabled { background: var(--bg); color: var(--muted); }
.actions { display: flex; justify-content: flex-end; margin-top: 10px; }
.msg { padding: 9px 12px; border-radius: 5px; margin: 10px 0; font-size: 12px; }
.msg.err { background: var(--red-soft); color: var(--red); }
.msg.ok { background: var(--green-soft); color: var(--green); }
.empty { padding: 20px; text-align: center; color: var(--muted); }
@media (max-width: 600px) { .form-grid { grid-template-columns: 1fr; } }
</style>
