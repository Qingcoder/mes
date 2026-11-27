<template>
  <section class="proto-board">
    <div class="proto-head">
      <div>
        <h3>{{ proto.title }}</h3>
        <p>前端基础雏形：展示页面结构、交互入口与数据占位，当前不接入业务数据。</p>
      </div>
      <div class="proto-actions">
        <button v-for="action in proto.actions" :key="action" class="btn sm" type="button" @click="trigger(action)">{{ action }}</button>
      </div>
    </div>

    <div v-if="notice" class="msg ok proto-notice">{{ notice }}</div>

    <div class="proto-tabs" role="tablist">
      <button
        v-for="tab in proto.tabs"
        :key="tab"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab"
        :class="{ active: activeTab === tab }"
        @click="activeTab = tab"
      >{{ tab }}</button>
    </div>

    <div class="proto-layout">
      <aside class="proto-side">
        <div class="side-title">模块导航</div>
        <button
          v-for="section in proto.sections"
          :key="section"
          type="button"
          :class="{ active: activeSection === section }"
          @click="selectSection(section)"
        >{{ section }}</button>
      </aside>

      <main class="proto-main">
        <div class="proto-toolbar">
          <input v-model="keyword" placeholder="输入关键词筛选（原型交互）" @keyup.enter="trigger('查询')" />
          <button class="btn sm primary" type="button" @click="trigger('查询')">查询</button>
          <button class="btn sm" type="button" @click="reset">重置</button>
        </div>

        <div class="proto-cards">
          <div class="proto-card">
            <label>当前模块</label><b>{{ activeSection }}</b>
            <small>结构占位</small>
          </div>
          <div class="proto-card">
            <label>当前视图</label><b>{{ activeTab }}</b>
            <small>可切换</small>
          </div>
          <div class="proto-card">
            <label>数据状态</label><b>{{ skeletonMeta ? '骨架已连接' : '待接入' }}</b>
            <small>{{ skeletonMeta ? `占位记录 ${records.length} 条` : '不展示假数据' }}</small>
          </div>
        </div>

        <div class="proto-panel">
          <div class="panel-title">{{ activeTab }} · {{ activeSection }}</div>
          <template v-if="records.length">
            <div v-for="r in records" :key="r.id" class="skeleton-row">
              <span class="sk-dot"></span>
              <b>{{ recordTitle(r) }}</b>
              <small class="mono">{{ r.id }}</small>
              <button class="link" type="button" @click="removeRecord(r)">删除</button>
            </div>
          </template>
          <template v-else>
            <div v-for="n in 4" :key="n" class="skeleton-row">
              <span class="sk-dot"></span>
              <span class="sk-line wide"></span>
              <span class="sk-line"></span>
              <span class="sk-pill"></span>
            </div>
          </template>
          <div class="empty-note">{{ apiError || '列表区域为交互骨架，可通过“新增”创建占位记录。' }}</div>
        </div>
      </main>

      <aside class="proto-detail">
        <div class="side-title">详情 / 操作区</div>
        <div class="detail-empty">选择列表项后展示详情</div>
        <div v-for="field in proto.detailFields" :key="field" class="detail-field">
          <label>{{ field }}</label>
          <span class="sk-line wide"></span>
        </div>
        <div class="detail-actions">
          <button class="btn sm" type="button" @click="trigger('编辑')">编辑</button>
          <button class="btn sm danger" type="button" @click="trigger('删除')">删除</button>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api'
import { domainPrototypeFor } from '../config/domainPrototype'

const props = defineProps<{ domainKey: string }>()

const proto = computed(() => domainPrototypeFor(props.domainKey))
const activeTab = ref(proto.value.tabs[0] || '概览')
const activeSection = ref(proto.value.sections[0] || '')
const keyword = ref('')
const notice = ref('')
const skeletonMeta = ref<any>(null)
const records = ref<any[]>([])
const apiError = ref('')
let timer: ReturnType<typeof setTimeout> | null = null

function showNotice(text: string) {
  notice.value = text
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => { notice.value = '' }, 2400)
}

function selectSection(section: string) {
  activeSection.value = section
  showNotice(`已切换到「${section}」模块`)
}

function recordTitle(r: any) {
  return r?.data?.title || r?.data?.name || '骨架记录'
}

async function loadSkeleton() {
  apiError.value = ''
  try {
    skeletonMeta.value = await api.moduleSkeletonMeta(props.domainKey)
    const data: any = await api.moduleSkeletonRecords(props.domainKey)
    records.value = data.items || []
  } catch (e: any) {
    apiError.value = e.message || '骨架接口不可用'
  }
}

async function addRecord() {
  try {
    await api.createModuleSkeletonRecord(props.domainKey, {
      title: `${activeSection.value} · 占位记录`,
      view: activeTab.value,
    })
    await loadSkeleton()
    showNotice('已创建一条骨架占位记录')
  } catch (e: any) { showNotice(e.message || '新增骨架记录失败') }
}

async function removeRecord(r: any) {
  try {
    await api.deleteModuleSkeletonRecord(props.domainKey, r.id)
    await loadSkeleton()
    showNotice('已删除骨架占位记录')
  } catch (e: any) { showNotice(e.message || '删除骨架记录失败') }
}

async function trigger(action: string) {
  if (action === '新增') { await addRecord(); return }
  if (action === '刷新') { await loadSkeleton(); showNotice('骨架记录已刷新'); return }
  const suffix = keyword.value.trim() ? `，关键词：${keyword.value.trim()}` : ''
  const messages: Record<string, string> = {
    '导入': '已触发导入交互，等待接入业务接口',
    '导出': '已触发展开导出交互，等待接入业务接口',
    '查询': `已触发查询交互${suffix}`,
    '编辑': '已触发编辑交互，等待接入业务接口',
    '删除': '已触发删除交互，等待接入业务接口',
  }
  showNotice(messages[action] || `已触发「${action}」交互`)
}

function reset() {
  keyword.value = ''
  activeTab.value = proto.value.tabs[0] || '概览'
  activeSection.value = proto.value.sections[0] || ''
  showNotice('原型状态已重置')
}

onMounted(loadSkeleton)
onUnmounted(() => { if (timer) clearTimeout(timer) })
</script>

<style scoped>
.proto-board { border: 1px solid var(--line); border-radius: 10px; background: var(--white); padding: 16px; margin-top: 14px; }
.proto-head { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; margin-bottom: 12px; }
.proto-head h3 { font-size: 17px; }
.proto-head p { margin-top: 5px; color: var(--muted); font-size: 12px; line-height: 1.6; }
.proto-actions { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.proto-notice { margin-bottom: 10px; }
.proto-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); margin-bottom: 12px; flex-wrap: wrap; }
.proto-tabs button { border: 0; background: transparent; color: var(--muted); padding: 7px 13px; cursor: pointer; font-family: inherit; }
.proto-tabs button.active { color: var(--red); border-bottom: 2px solid var(--red); font-weight: 700; }
.proto-layout { display: grid; grid-template-columns: 180px minmax(0, 1fr) 240px; gap: 12px; }
.proto-side, .proto-detail { border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: #fafbfc; }
.side-title { font-size: 12px; color: var(--muted); margin-bottom: 8px; }
.proto-side button { display: block; width: 100%; text-align: left; border: 0; background: transparent; padding: 8px 9px; border-radius: 6px; cursor: pointer; color: var(--ink); font-family: inherit; font-size: 13px; margin-bottom: 3px; }
.proto-side button.active { background: var(--tech-blue-soft); color: var(--tech-blue); font-weight: 700; }
.proto-toolbar { display: flex; gap: 6px; margin-bottom: 10px; }
.proto-toolbar input { flex: 1; min-width: 0; }
.proto-cards { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 8px; margin-bottom: 10px; }
.proto-card { border: 1px solid var(--line); border-radius: 8px; padding: 10px; }
.proto-card label, .detail-field label { display: block; font-size: 11px; color: var(--muted); margin-bottom: 4px; }
.proto-card b { font-size: 14px; }
.proto-card small { display: block; font-size: 11px; color: var(--muted); margin-top: 4px; }
.proto-panel { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.panel-title { padding: 9px 12px; background: #f7f8fa; border-bottom: 1px solid var(--line); font-size: 13px; font-weight: 600; }
.skeleton-row { display: flex; align-items: center; gap: 8px; padding: 12px; border-bottom: 1px solid var(--line); }
.skeleton-row:last-of-type { border-bottom: 0; }
.skeleton-row b { font-size: 13px; }
.skeleton-row small { color: var(--muted); max-width: 40%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.skeleton-row .link { margin-left: auto; border: 0; background: transparent; color: var(--red); cursor: pointer; font-size: 12px; }
.sk-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--tech-blue-soft); border: 1px solid var(--tech-blue-line); flex: none; }
.sk-line { display: block; height: 9px; width: 80px; border-radius: 5px; background: #eceff3; }
.sk-line.wide { flex: 1; max-width: 220px; }
.sk-pill { width: 46px; height: 16px; border-radius: 9px; background: #f1f2f4; }
.empty-note { padding: 12px; color: var(--muted); font-size: 12px; border-top: 1px dashed var(--line); }
.detail-empty { color: var(--muted); font-size: 12px; padding: 10px; border: 1px dashed var(--line); border-radius: 6px; margin-bottom: 10px; }
.detail-field { margin-bottom: 9px; }
.detail-actions { display: flex; gap: 6px; margin-top: 12px; }
.btn.sm { padding: 5px 10px; font-size: 12px; }
@media (max-width: 1180px) { .proto-layout { grid-template-columns: 170px minmax(0,1fr); } .proto-detail { grid-column: 1 / -1; } }
@media (max-width: 900px) { .proto-layout { grid-template-columns: minmax(0,1fr); } .proto-side { display: flex; gap: 6px; flex-wrap: wrap; } .proto-side button { width: auto; margin: 0; } }
@media (max-width: 768px) {
  .proto-head { flex-direction: column; }
  .proto-actions { justify-content: flex-start; }
  .proto-layout { grid-template-columns: 1fr; }
  .proto-cards { grid-template-columns: 1fr; }
}
</style>
