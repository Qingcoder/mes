<template>
  <div class="approve-page">
    <div class="approve-card">
      <div class="ap-icon">✓</div>
      <h2>扫码登录确认</h2>
      <p v-if="!done" class="ap-sub">请确认是否登录到戴盟 MES 生产管理平台</p>
      <p v-else class="ap-sub ok">已确认，可返回电脑端</p>

      <div v-if="!done" class="ap-info">
        <div class="ap-row"><span>会话</span><b class="mono">{{ sid.slice(0, 12) }}…</b></div>
        <div class="ap-row"><span>确认身份</span><b>{{ phoneUser?.name || '当前用户' }}</b></div>
        <div class="ap-row"><span>有效期</span><b>5 分钟</b></div>
      </div>

      <div v-if="error" class="msg err">{{ error }}</div>
      <div v-if="needLogin" class="msg err">请先在手机上登录 MES 后再确认</div>

      <button v-if="needLogin" class="btn primary ap-btn" @click="goLogin">去登录</button>
      <button v-else-if="!done" class="btn primary ap-btn" @click="approve" :disabled="busy">
        {{ busy ? '确认中…' : '确认登录' }}
      </button>
      <p class="ap-foot">仅在你主动扫码后才会授权，请勿确认未知来源的请求</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getToken, getUser, api } from '../api'

const phoneUser = getUser()

const route = useRoute()
const router = useRouter()
const sid = String(route.query.sid || '')
const needLogin = ref(!getToken())
const done = ref(false)
const busy = ref(false)
const error = ref('')

function goLogin() {
  router.push({ path: '/login', query: { redirect: route.fullPath } })
}

async function approve() {
  if (!sid) { error.value = '二维码参数缺失'; return }
  if (!getToken()) { error.value = '请先在手机上登录 MES 后再确认'; return }
  busy.value = true; error.value = ''
  try {
    await api.qrConfirm(sid)
    done.value = true
  } catch (e: any) { error.value = e.message || '确认失败' }
  finally { busy.value = false }
}
</script>

<style scoped>
.approve-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px;
  background: radial-gradient(120% 105% at 50% 48%, #10224A 0%, #091735 44%, #040B1C 100%); }
.approve-card { width: 100%; max-width: 340px; background: rgba(255,255,255,.96); border-radius: 14px; padding: 30px 26px; text-align: center;
  box-shadow: 0 24px 60px rgba(0,0,0,.4), 0 0 0 1px rgba(46,111,232,.3); }
.ap-icon { width: 52px; height: 52px; border-radius: 50%; background: var(--tech-blue); color: #fff; font-size: 26px;
  display: grid; place-items: center; margin: 0 auto 16px; box-shadow: 0 0 18px rgba(46,111,232,.4); }
.approve-card h2 { font-size: 19px; color: var(--ink); margin-bottom: 8px; }
.ap-sub { font-size: 13px; color: var(--muted); line-height: 1.7; margin-bottom: 20px; }
.ap-sub.ok { color: var(--green); }
.ap-info { background: var(--tech-blue-soft); border-radius: 8px; padding: 12px 14px; margin-bottom: 18px; }
.ap-row { display: flex; justify-content: space-between; padding: 5px 0; font-size: 13px; }
.ap-row span { color: var(--muted); }
.ap-row b { color: var(--ink); }
.ap-btn { width: 100%; }
.ap-foot { margin-top: 16px; font-size: 11px; color: var(--muted); line-height: 1.6; }
</style>
