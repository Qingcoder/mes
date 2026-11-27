<template>
  <div class="role-create-page">
    <div class="role-create-card">
      <div class="head">
        <h2>创建角色</h2>
        <button class="btn sm" type="button" @click="router.push('/person')">返回人员管理</button>
      </div>
      <p class="sub">独立备用页面；当前入口在人员管理页弹窗中打开。</p>
      <RoleCombinationForm @created="onCreated" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import RoleCombinationForm from '../components/RoleCombinationForm.vue'

const router = useRouter()

function onCreated() {
  // 独立页仅作为备用入口，创建结果由共享组件展示。
}
</script>

<style scoped>
.role-create-page { min-height: 100vh; display: grid; place-items: center; padding: 20px; background: var(--bg); }
.role-create-card { width: min(560px, 100%); background: var(--white); border: 1px solid var(--line); border-radius: 12px; padding: 22px; }
.head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.head h2 { font-size: 20px; }
.sub { margin: 8px 0 16px; color: var(--muted); font-size: 13px; }
.btn.sm { padding: 5px 10px; font-size: 12px; }
</style>
