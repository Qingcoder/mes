<template>
  <div class="sn-library">
    <div class="head">
      <div>
        <h2>SN 库</h2>
        <p class="sub">数据来自产品资料总表；在产品资料导入 SN 后自动汇总，本页只读。</p>
      </div>
      <div class="row">
        <button class="btn" type="button" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <div v-if="error" class="msg err">{{ error }}</div>

    <div class="stats">
      <article><span>SN 总数（已去重）</span><b>{{ summary.total || 0 }}</b></article>
      <article><span>关联产品</span><b>{{ (summary.products || []).length }}</b></article>
      <article><span>重复组 / 去重条数</span><b>{{ summary.duplicateGroups || 0 }} / {{ summary.duplicateRemoved || 0 }}</b></article>
    </div>

    <details v-if="(summary.duplicates || []).length" class="dup-panel">
      <summary>
        <b>检测到 {{ summary.duplicateGroups || 0 }} 组重复 SN，已去重 {{ summary.duplicateRemoved || 0 }} 条；SN 库仅保留首次出现的记录。</b>
        <span class="mini">点击展开明细</span>
      </summary>
      <div v-for="group in visibleDuplicates" :key="group.sn" class="dup-row">
        <b class="mono">{{ group.sn }}</b>
        <span>共 {{ group.count }} 处，去掉 {{ group.removed }} 条重复：</span>
        <span v-for="(source, index) in group.sources" :key="index" class="dup-source">
          {{ source.product || '—' }} / {{ source.sideName || '—' }} / {{ source.sourceFile || '—' }}
        </span>
      </div>
      <button v-if="filteredDuplicates.length > 20" class="link" type="button" @click="showAllDuplicates = !showAllDuplicates">
        {{ showAllDuplicates ? '收起明细' : `展开全部 ${filteredDuplicates.length} 组` }}
      </button>
    </details>

    <div class="toolbar">
      <label>关键词<input v-model="filters.keyword" placeholder="SN / 产品 / 件别 / 来源文件" @keyup.enter="applyFilters" /></label>
      <label>件别
        <select v-model="filters.sideName" @change="applyFilters">
          <option value="">全部件别</option>
          <option v-for="item in sideCategories" :key="item.name" :value="item.name">{{ item.name }}（{{ item.count }}）</option>
        </select>
      </label>
      <label>每页
        <select v-model.number="pageSize" @change="applyFilters">
          <option :value="20">20</option><option :value="50">50</option><option :value="100">100</option>
        </select>
      </label>
      <button class="btn" type="button" @click="applyFilters">查询</button>
      <button class="btn" type="button" @click="resetFilters">重置</button>
      <span class="mini">筛选结果 {{ filteredRows.length }} 条</span>
    </div>

    <div class="category-bar">
      <span>产品分类</span>
      <button v-for="item in productCategories" :key="item.name" type="button" :class="{ active: filters.product === item.name }" @click="selectProduct(item.name)">
        {{ item.name }} <small>{{ item.count }}</small>
      </button>
    </div>

    <div class="table-scroll">
      <table>
        <thead><tr><th>SN 编码</th><th>产品</th><th>件别</th><th>来源文件</th><th>更新时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="row in pagedRows" :key="row.id">
            <td class="mono">{{ row.sn }}</td>
            <td>{{ row.product || '—' }}</td>
            <td>{{ row.sideName || '—' }}</td>
            <td class="mini">{{ row.sourceFile || '—' }}</td>
            <td class="mono">{{ fmt(row.updatedAt) }}</td>
            <td class="ops">
              <router-link class="link" :to="{ path: '/product-info', query: { product: row.product } }">查看产品</router-link>
            </td>
          </tr>
          <tr v-if="!pagedRows.length"><td colspan="6" class="empty">暂无 SN 记录，请先在产品资料中导入 SN</td></tr>
        </tbody>
      </table>
    </div>

    <div class="pager">
      <button class="btn sm" type="button" :disabled="page <= 1" @click="page -= 1">上一页</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button class="btn sm" type="button" :disabled="page >= totalPages" @click="page += 1">下一页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { api, friendlyError } from '../api'

const rows = ref<any[]>([])
const summary = ref<any>({ total: 0, products: [], duplicateGroups: 0, duplicateRemoved: 0, duplicates: [] })
const filters = reactive({ keyword: '', product: '', sideName: '' })
const loading = ref(false)
const error = ref('')
const showAllDuplicates = ref(false)
const page = ref(1)
const pageSize = ref(20)
const filteredDuplicates = computed(() => {
  const q = filters.keyword.trim().toLowerCase()
  const groups = summary.value.duplicates || []
  if (!q) return groups
  return groups.filter((group: any) => `${group.sn} ${(group.sources || []).map((s: any) => `${s.product || ''} ${s.sideName || ''} ${s.sourceFile || ''}`).join(' ')}`.toLowerCase().includes(q))
})
const visibleDuplicates = computed(() => showAllDuplicates.value ? filteredDuplicates.value : filteredDuplicates.value.slice(0, 20))
const productCategories = computed(() => {
  const map = new Map<string, number>()
  rows.value.forEach((row: any) => {
    const name = String(row.product || '未分类')
    map.set(name, (map.get(name) || 0) + 1)
  })
  return Array.from(map, ([name, count]) => ({ name, count }))
})
const sideCategories = computed(() => {
  const source = rows.value.filter((row: any) => !filters.product || String(row.product || '未分类') === filters.product)
  const map = new Map<string, number>()
  source.forEach((row: any) => {
    const name = String(row.sideName || '未分类')
    map.set(name, (map.get(name) || 0) + 1)
  })
  return Array.from(map, ([name, count]) => ({ name, count }))
})
const filteredRows = computed(() => {
  const q = filters.keyword.trim().toLowerCase()
  return rows.value.filter((row: any) => {
    if (filters.product && String(row.product || '未分类') !== filters.product) return false
    if (filters.sideName && String(row.sideName || '未分类') !== filters.sideName) return false
    if (!q) return true
    return `${row.sn || ''} ${row.product || ''} ${row.sideName || ''} ${row.sourceFile || ''}`.toLowerCase().includes(q)
  })
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value)))
const pagedRows = computed(() => filteredRows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))

watch([() => filters.keyword, () => filters.product, () => filters.sideName, pageSize], () => { page.value = 1 })

function selectProduct(name: string) {
  filters.product = filters.product === name ? '' : name
  filters.sideName = ''
  page.value = 1
}
function applyFilters() {
  page.value = 1
}
function fmt(value: string) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [list, stats] = await Promise.all([
      api.snLibraryRecords(),
      api.snLibrarySummary(),
    ])
    rows.value = list
    summary.value = stats
  } catch (e: any) {
    error.value = friendlyError(e, 'SN 库加载失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.keyword = ''
  filters.product = ''
  filters.sideName = ''
  pageSize.value = 20
  page.value = 1
}

function refreshWhenVisible() {
  if (document.visibilityState === 'visible') void load()
}
onMounted(() => {
  load()
  window.addEventListener('focus', refreshWhenVisible)
})
onUnmounted(() => window.removeEventListener('focus', refreshWhenVisible))
</script>

<style scoped>
.sn-library { max-width: 1180px; margin: 0 auto; }
.head, .panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
h2 { font-size: 20px; }
.sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
.row, .toolbar, .modal-foot { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin: 12px 0; }
.stats article { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; background: var(--white); display: grid; gap: 4px; }
.stats span { color: var(--muted); font-size: 11px; }
.stats b { font-size: 18px; }
.dup-panel { border: 1px solid var(--red-soft); background: var(--red-soft); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-size: 12px; line-height: 1.6; }
.dup-panel summary { cursor: pointer; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.dup-panel summary .mini { margin-left: auto; color: var(--muted); }
.dup-panel > .link { margin-top: 8px; }
.dup-row { display: flex; flex-wrap: wrap; gap: 6px 10px; margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(0,0,0,.06); }
.dup-source { color: var(--muted); }
.toolbar { margin-bottom: 10px; }
.category-bar { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; padding: 9px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--white); font-size: 12px; }
.category-bar > span { color: var(--muted); flex: none; }
.category-bar button { border: 1px solid var(--line); background: var(--white); color: var(--ink); border-radius: 999px; padding: 5px 10px; font-family: inherit; font-size: 12px; cursor: pointer; }
.category-bar button.active { border-color: var(--tech-blue-line); background: var(--tech-blue-soft); color: var(--tech-blue); font-weight: 600; }
.category-bar small { color: var(--muted); margin-left: 4px; }
.toolbar label { display: flex; gap: 6px; align-items: center; color: var(--muted); font-size: 12px; }
.toolbar input, .toolbar select { width: auto; min-width: 180px; }
.table-scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--white); }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; }
th { color: var(--muted); }
.ops { white-space: nowrap; }
.link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; font-family: inherit; font-size: 11px; }
.danger-link { color: var(--red); }
.empty { color: var(--muted); }
.pager { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 12px; font-size: 12px; color: var(--muted); }
.msg { padding: 9px 12px; border-radius: 5px; margin-bottom: 10px; }
.msg.err { background: var(--red-soft); color: var(--red); }
.msg.ok { background: var(--green-soft); color: var(--green); }
.modal-mask { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(4,8,18,.65); }
.modal { width: 100%; max-width: 460px; background: var(--white); border-radius: 10px; padding: 18px; }
.modal label { display: grid; gap: 5px; color: var(--muted); font-size: 12px; margin-top: 12px; }
input, textarea, select { border: 1px solid var(--line); border-radius: 6px; padding: 8px; font-family: inherit; color: var(--ink); background: var(--white); }
.modal-foot { justify-content: flex-end; margin-top: 14px; }
@media (max-width: 700px) { .head { flex-direction: column; } .toolbar label { width: 100%; } .toolbar input, .toolbar select { width: 100%; } .category-bar > span { width: 100%; } }
</style>
