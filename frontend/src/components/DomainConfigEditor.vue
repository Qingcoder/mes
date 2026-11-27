<template>
  <div class="domain-config">
    <div class="domain-note">
      <b>人机料法环配置编辑区</b>
      <p>先在这里填写模块名称、目标路由、菜单分组、权限码和关联说明。当前只保存配置，不会自动生成路由、菜单或权限逻辑；你编辑完成后我再按这份配置落地真实页面。</p>
    </div>

    <div class="domain-summary">
      <span v-for="d in domains" :key="d.key">{{ d.name }}<small>{{ d.route || '路由待填' }}</small></span>
    </div>

    <div class="domain-toolbar">
      <span class="mini">保存人：{{ config.updatedBy || '—' }} · 更新时间：{{ formatTime(config.updatedAt) }}</span>
      <div class="row">
        <button class="btn sm" type="button" @click="formatText">格式化</button>
        <button class="btn sm" type="button" :disabled="loading" @click="load">重新加载</button>
        <button class="btn primary sm" type="button" :disabled="!canManage || saving" @click="save">
          {{ saving ? '保存中…' : '保存配置' }}
        </button>
      </div>
    </div>

    <div v-if="!canManage" class="msg err">当前账号无人机料法环配置权限。</div>
    <div v-if="error" class="msg err">{{ error }}</div>
    <div v-if="message" class="msg ok">{{ message }}</div>

    <textarea
      v-model="text"
      class="domain-editor mono"
      spellcheck="false"
      :disabled="!canManage || loading"
      aria-label="人机料法环配置编辑框"
    />
    <p class="mini">保留字段：key、name、route、menuGroup、permission、description、children、relations、notes。路由可以留空，当前不会注册。</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const props = defineProps<{ canManage: boolean }>()

const config = ref<any>({ domains: [], updatedAt: '', updatedBy: '' })
const text = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const domains = computed<any[]>(() => Array.isArray(config.value.domains) ? config.value.domains : [])

function formatTime(v?: string) {
  return v ? new Date(v).toLocaleString('zh-CN') : '—'
}

function setEditor(data: any) {
  config.value = data || { domains: [] }
  text.value = JSON.stringify({ domains: config.value.domains || [] }, null, 2)
}

async function load() {
  if (!props.canManage) return
  loading.value = true; error.value = ''; message.value = ''
  try {
    setEditor(await api.domainConfig())
  } catch (e: any) {
    error.value = e.message || '配置加载失败'
  } finally {
    loading.value = false
  }
}

function formatText() {
  error.value = ''; message.value = ''
  try {
    const parsed = JSON.parse(text.value || '{}')
    text.value = JSON.stringify(parsed, null, 2)
    message.value = '格式已整理，尚未保存'
  } catch (e: any) {
    error.value = `JSON 格式错误：${e?.message || '请检查括号与引号'}`
  }
}

async function save() {
  if (!props.canManage) return
  error.value = ''; message.value = ''
  let parsed: any
  try {
    parsed = JSON.parse(text.value || '{}')
  } catch (e: any) {
    error.value = `JSON 格式错误：${e?.message || '请检查括号与引号'}`
    return
  }
  if (!Array.isArray(parsed.domains) || parsed.domains.length !== 5) {
    error.value = '配置必须包含 domains 数组，并保持人机料法环 5 个领域'
    return
  }
  saving.value = true
  try {
    const saved: any = await api.saveDomainConfig(parsed.domains)
    setEditor(saved)
    message.value = '配置已保存；当前仅保存结构，尚未生成真实路由'
  } catch (e: any) {
    error.value = e.message || '配置保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.domain-config { border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; }
.domain-note { border-left: 3px solid var(--tech-blue); padding: 2px 0 2px 10px; margin-bottom: 12px; }
.domain-note p { margin: 5px 0 0; font-size: 12px; color: var(--muted); line-height: 1.65; }
.domain-summary { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.domain-summary span { display: inline-flex; align-items: center; gap: 6px; padding: 5px 9px; border: 1px solid var(--line); border-radius: 14px; font-size: 12px; }
.domain-summary small { color: var(--muted); }
.domain-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.domain-toolbar .row { display: flex; gap: 6px; flex-wrap: wrap; }
.domain-editor { width: 100%; min-height: 420px; resize: vertical; padding: 14px; border: 1px solid var(--line); border-radius: 8px; background: #f8f9fb; color: var(--ink); line-height: 1.6; font-size: 13px; outline: none; }
.domain-editor:focus { border-color: var(--tech-blue); box-shadow: 0 0 0 3px var(--tech-blue-soft); }
.btn.sm { padding: 5px 10px; font-size: 12px; }
@media (max-width: 768px) { .domain-editor { min-height: 340px; font-size: 12px; } .domain-toolbar { align-items: stretch; } }
</style>
