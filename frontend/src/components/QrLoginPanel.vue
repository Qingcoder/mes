<template>
  <div class="auth-form qr-pane">
    <div class="qr-box">
      <img v-if="qrDataUrl" :src="qrDataUrl" alt="扫码登录二维码" />
      <div v-else class="qr-loading">{{ message || '生成二维码…' }}</div>
    </div>
    <p class="qr-tip">用已登录的手机扫一扫，确认后自动登录</p>
    <button class="btn ghost" type="button" @click="emit('refresh')">刷新二维码</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  qrDataUrl: string
  message?: string
}>()

const emit = defineEmits<{
  refresh: []
}>()
</script>
