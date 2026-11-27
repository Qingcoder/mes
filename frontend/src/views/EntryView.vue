<template>
  <div class="entry-page">
    <div class="entry-card">
      <h1>戴盟 MES</h1>
      <p>请使用系统账号登录</p>
      <div class="entry-actions">
        <button class="btn primary" type="button" @click="router.push('/login')">登录</button>
      </div>
      <small>登录后进入系统首页</small>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
.entry-page { min-height: 100vh; display: grid; place-items: center; padding: 20px; background: var(--bg); }
.entry-card { width: min(420px, 100%); background: var(--white); border: 1px solid var(--line); border-radius: 12px; padding: 32px; text-align: center; box-shadow: 0 12px 40px rgba(0,0,0,.06); }
.entry-card h1 { font-size: 24px; letter-spacing: 1px; }
.entry-card p { margin: 10px 0 28px; color: var(--muted); font-size: 14px; }
.entry-actions { display: grid; gap: 12px; }
.entry-actions .btn { width: 100%; }
.entry-card small { display: block; margin-top: 22px; color: var(--muted); font-size: 12px; }
</style>
