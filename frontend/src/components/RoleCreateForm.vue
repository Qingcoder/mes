<template>
  <div ref="rootRef" class="role-create-form" :aria-busy="loading || loadingConfig">
    <div v-if="loadingConfig" class="msg">正在加载角色编码、模板与权限树…</div>
    <div v-else-if="configError" class="msg err">{{ configError }}</div>

    <template v-else>
      <div class="code-line">角色编码：<b class="mono">{{ nextCode || '自动生成' }}</b></div>

      <div class="field">
        <label for="role-template">角色模板</label>
        <p class="hint">选择预设模板后立即创建；如需自定义，选择“创建模板（自定义）”。</p>
        <select id="role-template" v-model="selectedTemplateId" :disabled="loading" @change="onTemplateChange">
          <option value="">请选择角色模板</option>
          <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">{{ tpl.name }}</option>
        </select>
      </div>

      <div v-if="selectedTemplate && !selectedTemplate.custom" class="template-summary">
        <b>{{ selectedTemplate.avatar }} {{ selectedTemplate.name }}</b>
        <p>{{ selectedTemplate.description }}</p>
        <small>已选 {{ selectedTemplate.functions.length }} 项功能，选择后立即创建。</small>
      </div>

      <template v-if="isCustom">
        <div class="field">
          <label for="role-name">模板名称</label>
          <input
            id="role-name"
            v-model="customName"
            maxlength="64"
            autocomplete="off"
            placeholder="输入模板名称后按回车或移开焦点即创建"
            :disabled="loading"
            @keydown.enter.prevent="submitCustom"
            @blur="submitCustom"
          />
          <p class="hint">仅在创建模板时显示输入字段；输入完成后自动创建。</p>
        </div>

        <div class="field">
          <label>可用功能</label>
          <FunctionTreeSelect v-model="selectedFunctions" :nodes="functionNodes" />
        </div>
      </template>

      <div v-if="error" class="msg err" role="alert">{{ error }}</div>
      <div v-if="created" class="msg ok" role="status">
        角色创建成功：{{ created.avatar }} {{ created.code }} · {{ created.name }}
        <button class="link inline" type="button" @click="emit('viewRoles')">查看角色列表</button>
      </div>
      <div v-if="generated" class="msg" role="status">已生成 {{ generated.permissions?.length || 0 }} 项权限、{{ generated.routes?.length || 0 }} 条路由配置</div>

      <div v-if="created" class="module-section">
        <h3>该角色可支配的下一级功能模块</h3>
        <div v-if="generated?.functions?.length" class="module-grid">
          <div v-for="fn in generated.functions" :key="fn.id" class="module-card">
            <b>{{ fn.name }}</b>
            <p>{{ fn.description || '暂无模块说明' }}</p>
            <small class="mono">{{ fn.route || '无独立路由' }}</small>
          </div>
        </div>
        <div v-else class="empty">该角色暂无可支配的功能模块</div>
      </div>

      <div v-if="showCancel" class="form-foot">
        <button class="btn" type="button" :disabled="loading" @click="emit('cancel')">关闭</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import FunctionTreeSelect from './FunctionTreeSelect.vue'

const props = withDefaults(defineProps<{ showCancel?: boolean }>(), { showCancel: false })
const emit = defineEmits<{
  cancel: []
  created: [value: any]
  'update:submitting': [value: boolean]
  viewRoles: []
}>()

const rootRef = ref<HTMLElement | null>(null)
const nextCode = ref('')
const error = ref('')
const loading = ref(false)
const loadingConfig = ref(true)
const configError = ref('')
const created = ref<any>(null)
const functionNodes = ref<any[]>([])
const templates = ref<any[]>([])
const selectedTemplateId = ref('')
const customName = ref('')
const selectedFunctions = ref<string[]>([])
const generated = ref<any>(null)

const selectedTemplate = computed(() => templates.value.find(t => t.id === selectedTemplateId.value) || null)
const isCustom = computed(() => !!selectedTemplate.value?.custom)

async function loadConfig() {
  loadingConfig.value = true
  configError.value = ''
  try {
    const [codeResult, treeResult, templateResult] = await Promise.allSettled([
      api.nextRoleCode(),
      api.functionTree(),
      api.roleTemplates(),
    ])
    if (codeResult.status === 'fulfilled') nextCode.value = (codeResult.value as any)?.code || ''
    if (treeResult.status === 'fulfilled') functionNodes.value = ((treeResult.value as any)?.nodes || []) as any[]
    if (templateResult.status === 'fulfilled') templates.value = ((templateResult.value as any)?.items || []) as any[]
    const failed = [codeResult, treeResult, templateResult].filter(r => r.status === 'rejected').length
    if (failed) configError.value = '初始化数据未完全加载，请刷新后重试。'
  } finally {
    loadingConfig.value = false
  }
}

async function createRole(payload: any) {
  if (loading.value || loadingConfig.value) return
  error.value = ''; created.value = null
  loading.value = true
  emit('update:submitting', true)
  try {
    created.value = await api.createRole(payload)
    generated.value = await api.functionRoutes()
    emit('created', created.value)
    const r: any = await api.nextRoleCode()
    nextCode.value = r.code || ''
  } catch (e: any) {
    error.value = e.message || '角色创建失败'
  } finally {
    loading.value = false
    emit('update:submitting', false)
  }
}

async function onTemplateChange() {
  const tpl = selectedTemplate.value
  if (!tpl || loading.value) return
  error.value = ''; created.value = null
  if (tpl.custom) {
    customName.value = ''
    selectedFunctions.value = []
    return
  }
  const suffix = nextCode.value ? `-${nextCode.value}` : ''
  await createRole({
    name: `${tpl.name}${suffix}`.slice(0, 64),
    description: tpl.description || '',
    avatar: tpl.avatar || tpl.name.slice(0, 1),
    functions: [...(tpl.functions || [])],
  })
  selectedTemplateId.value = ''
}

async function submitCustom() {
  if (!isCustom.value || loading.value || loadingConfig.value) return
  const name = customName.value.trim()
  if (!name) return
  const payload: any = {
    name,
    description: `自定义角色模板：${name}`,
    avatar: name.slice(0, 1),
  }
  if (selectedFunctions.value.length) payload.functions = [...selectedFunctions.value]
  await createRole(payload)
  customName.value = ''
  selectedFunctions.value = []
  selectedTemplateId.value = ''
}

watch(loadingConfig, async (value) => {
  if (value) return
  await nextTick()
  rootRef.value?.querySelector<HTMLElement>('#role-template')?.focus()
})

onMounted(loadConfig)
</script>

<style scoped>
.role-create-form { width: 100%; }
.code-line { font-size: 13px; margin-bottom: 14px; color: var(--muted); }
.field { margin-bottom: 12px; }
.hint { margin: 2px 0 8px; color: var(--muted); font-size: 12px; }
select { width: 100%; height: 38px; border: 1px solid var(--line); border-radius: 7px; padding: 0 10px; background: var(--white); color: var(--ink); }
.template-summary { border: 1px solid var(--tech-blue-line); background: var(--tech-blue-soft); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; }
.template-summary b { font-size: 13px; }
.template-summary p { color: var(--muted); font-size: 12px; margin: 4px 0; }
.template-summary small { color: var(--muted); font-size: 11px; }
.module-section { margin-top: 16px; border-top: 1px solid var(--line); padding-top: 14px; }
.module-section h3 { font-size: 15px; margin-bottom: 10px; }
.module-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; }
.module-card { border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: #fff; }
.module-card b { font-size: 13px; }
.module-card p { margin: 5px 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
.module-card small { color: var(--muted); font-size: 11px; }
.module-section .empty { color: var(--muted); font-size: 12px; padding: 14px; border: 1px dashed var(--line); border-radius: 8px; text-align: center; }
form label, label { display: block; font-size: 12px; color: var(--muted); margin: 0 0 5px; }
input, textarea { width: 100%; }
textarea { resize: vertical; }
.link.inline { margin-left: 8px; }
.form-foot { display: flex; gap: 8px; margin-top: 16px; }
@media (max-width: 768px) { .module-grid { grid-template-columns: 1fr; } }
</style>
