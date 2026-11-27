<template>
  <div class="domain-module">
    <div class="head">
      <div>
        <h2>{{ domain?.name || '领域模块' }}</h2>
        <p class="sub">{{ domain?.description || '领域说明未配置' }}</p>
      </div>
      <div class="row">
        <button class="btn" type="button" @click="router.push('/')">返回首页</button>
      </div>
    </div>

    <FixedModuleNotice v-if="domainKey !== 'machine' && domainKey !== 'environment'" :module-key="domainKey" />

    <div v-if="error" class="msg err">{{ error }}</div>
    <div v-else-if="loading" class="msg">加载领域配置…</div>
    <template v-else-if="domain">
      <div v-if="domainKey !== 'machine' && domainKey !== 'environment'" class="card">
        <div class="info-grid">
          <div><label>领域标识</label><b class="mono">{{ domain.key }}</b></div>
          <div><label>路由</label><b class="mono">{{ domain.route || '未配置' }}</b></div>
          <div><label>菜单分组</label><b>{{ domain.menuGroup || '未配置' }}</b></div>
          <div><label>权限码</label><b class="mono">{{ domain.permission || '未配置' }}</b></div>
        </div>
        <div v-if="domain.notes" class="notes"><label>备注</label><p>{{ domain.notes }}</p></div>
      </div>

      <EnvironmentResourcePanel v-if="domainKey === 'environment'" />
      <StationMasterPanel v-if="domainKey === 'environment'" />
      <MaterialProductPanel v-if="domainKey === 'material'" />
      <EquipmentPanel v-if="domainKey === 'machine'" />

      <DomainPrototypeBoard v-if="domainKey !== 'machine' && domainKey !== 'environment'" :domain-key="domainKey" />

      <div class="card">
        <h3>子模块</h3>
        <div v-if="children.length" class="list">
          <div v-for="(item, i) in children" :key="i" class="list-row">
            <span class="dot"></span><b>{{ typeof item === 'string' ? item : (item.name || item.label || item.key || '未命名模块') }}</b>
            <small class="mono">{{ typeof item === 'string' ? '' : (item.route || '') }}</small>
          </div>
        </div>
        <div v-else class="empty">当前未配置子模块</div>
      </div>

      <div class="card">
        <h3>关联关系</h3>
        <div v-if="relations.length" class="list">
          <div v-for="(item, i) in relations" :key="i" class="list-row">
            <span class="dot blue"></span><b>{{ typeof item === 'string' ? item : (item.name || item.relation || item.to || '未命名关系') }}</b>
            <small class="mono">{{ typeof item === 'string' ? '' : JSON.stringify(item) }}</small>
          </div>
        </div>
        <div v-else class="empty">当前未配置关联关系</div>
      </div>
    </template>
    <div v-else class="msg err">未在配置中找到当前领域：{{ domainKey }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import DomainPrototypeBoard from '../components/DomainPrototypeBoard.vue'
import FixedModuleNotice from '../components/FixedModuleNotice.vue'
import StationMasterPanel from '../components/StationMasterPanel.vue'
import MaterialProductPanel from '../components/MaterialProductPanel.vue'
import EnvironmentResourcePanel from '../components/EnvironmentResourcePanel.vue'
import EquipmentPanel from '../components/EquipmentPanel.vue'

const route = useRoute()
const router = useRouter()
const config = ref<any>({ domains: [] })
const loading = ref(false)
const error = ref('')
const domainKey = computed(() => String(route.name || ''))
const domain = computed(() => (config.value.domains || []).find((d: any) => d.key === domainKey.value))
const children = computed<any[]>(() => Array.isArray(domain.value?.children) ? domain.value.children : [])
const relations = computed<any[]>(() => Array.isArray(domain.value?.relations) ? domain.value.relations : [])

async function load() {
  loading.value = true; error.value = ''
  try {
    config.value = await api.domainConfig()
  } catch (e: any) {
    error.value = e.message || '领域配置加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.domain-module { max-width: 980px; margin: 0 auto; }
.head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 16px; }
.head h2 { font-size: 22px; }
.sub { color: var(--muted); font-size: 13px; margin-top: 6px; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
.card { background: var(--white); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.card h3 { margin-bottom: 10px; font-size: 16px; }
.info-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px 18px; }
.info-grid label, .notes label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.info-grid b { font-size: 14px; }
.notes { margin-top: 14px; border-top: 1px solid var(--line); padding-top: 12px; }
.notes p { line-height: 1.7; white-space: pre-wrap; }
.list-row { display: flex; align-items: center; gap: 8px; padding: 9px 0; border-bottom: 1px solid var(--line); }
.list-row:last-child { border-bottom: 0; }
.list-row small { margin-left: auto; color: var(--muted); max-width: 55%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--red); flex: none; }
.dot.blue { background: var(--tech-blue); }
.empty { color: var(--muted); font-size: 13px; padding: 12px 0; }
@media (max-width: 768px) { .head { flex-direction: column; } .info-grid { grid-template-columns: 1fr; } }
</style>
