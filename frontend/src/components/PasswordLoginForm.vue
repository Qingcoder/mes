<template>
  <form class="auth-form" @submit.prevent="emit('submit')">
    <div class="field">
      <label for="login-username">用户名</label>
      <input
        id="login-username"
        :value="username"
        autocomplete="username"
        placeholder="请输入账号"
        @input="emit('update:username', ($event.target as HTMLInputElement).value)"
      />
    </div>
    <div class="field">
      <label for="login-password">密码</label>
      <input
        id="login-password"
        :value="password"
        type="password"
        autocomplete="current-password"
        placeholder="请输入密码"
        @input="emit('update:password', ($event.target as HTMLInputElement).value)"
        @keyup.enter="emit('submit')"
      />
    </div>
    <div v-if="error" class="msg err">{{ error }}</div>
    <button class="btn primary" type="submit" :disabled="loading">
      {{ loading ? '登录中…' : '登录' }}
    </button>
  </form>
</template>

<script setup lang="ts">
defineProps<{
  username: string
  password: string
  loading: boolean
  error?: string
}>()

const emit = defineEmits<{
  'update:username': [value: string]
  'update:password': [value: string]
  submit: []
}>()
</script>
