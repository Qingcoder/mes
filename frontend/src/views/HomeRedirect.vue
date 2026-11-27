<template>
  <div class="home-redirect"></div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getPermissions, getToken } from '../api'
import { firstAllowedPath } from '../router/routeConfig'

const router = useRouter()

onMounted(() => {
  const target = getToken() ? firstAllowedPath(getPermissions()) : '/login'
  router.replace(target || '/login')
})
</script>

<style scoped>
.home-redirect { min-height: 100vh; background: var(--bg); }
</style>
