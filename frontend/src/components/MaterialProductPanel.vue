<template>
  <section class="card material-products">
    <div class="panel-head">
      <div>
        <h3>产品主数据</h3>
        <p class="sub">只需命名产品并导入 SN；编码和清单结构由系统自动生成。</p>
      </div>
      <div class="row">
        <button class="btn sm" type="button" :disabled="loading" @click="load">刷新</button>
        <button v-if="canManage" class="btn sm primary" type="button" @click="openForm()">新增产品</button>
      </div>
    </div>

    <div v-if="error" class="msg err">{{ error }}</div>
    <div v-if="notice" class="msg ok">{{ notice }}</div>
    <div v-if="!canManage" class="msg">当前账号无产品维护权限，仅可查看产品列表。</div>

    <div class="toolbar">
      <label>搜索<input v-model="keyword" placeholder="编码 / 名称" /></label>
      <span class="mini">共 {{ profiles.length }} 个产品</span>
    </div>

    <div class="table-scroll">
      <table>
        <thead><tr><th>编码</th><th>名称</th><th>SN</th><th>操作</th></tr></thead>
        <tbody>
          <tr
            v-for="row in filteredRows"
            :key="row.code"
            :class="{ editable: canManage }"
            :title="canManage ? '双击编辑产品名称' : ''"
            @dblclick="canManage && openForm(row)"
          >
            <td class="mono">{{ row.code }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.snCount || 0 }}</td>
            <td>
              <router-link class="link" :to="{ path: '/product-info', query: { code: row.code } }">导入 SN</router-link>
              <button v-if="canManage" class="link" type="button" @click="openForm(row)">改名</button>
              <button v-if="canManage" class="link danger-link" type="button" @click="removeRow(row)">删除</button>
            </td>
          </tr>
          <tr v-if="!filteredRows.length"><td colspan="4" class="empty">{{ profiles.length ? '未找到匹配的产品' : '暂无产品' }}</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="formOpen" class="modal-mask" @click.self="formOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <div class="panel-head">
          <b>{{ form.mode === 'create' ? '新增产品' : '修改产品名称' }}</b>
          <button class="btn sm" type="button" @click="formOpen = false">关闭</button>
        </div>
        <div v-if="formError" class="msg err">{{ formError }}</div>
        <p class="sub">产品编码由系统自动生成，SN 请到产品资料页导入。</p>
        <div class="form-grid single-grid">
          <label>产品名称<input v-model="form.name" placeholder="如：无本体数采夹爪" /></label>
        </div>
        <div class="modal-foot">
          <button class="btn" type="button" @click="formOpen = false">取消</button>
          <button class="btn primary" type="button" @click="save">保存产品</button>
        </div>
      </div>
    </div>

  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { getUser } from '../api'
import { sharedPerms } from '../stores/permStore'
import { useProductProfiles } from '../composables/useProductProfiles'

const keyword = ref('')
const formError = ref('')
const formOpen = ref(false)
const canManage = computed(() => getUser()?.role === 'admin' || sharedPerms.value.some(p => ['material:manage', 'wo:create'].includes(p)))

const { profiles, loading, error, notice, load, create, rename, remove, filterRows } = useProductProfiles()

const form = reactive<any>({ mode: 'create', code: '', name: '' })

const filteredRows = computed(() => filterRows(keyword.value))

async function save() {
  formError.value = ''
  const name = String(form.name || '').trim()
  if (!name) { formError.value = '请输入产品名称'; return }
  if (form.mode === 'create') {
    const created = await create(name)
    if (!created) { formError.value = error.value; return }
  } else {
    const ok = await rename(form.code, name)
    if (!ok) { formError.value = error.value; return }
  }
  formOpen.value = false
}
async function removeRow(row: any) {
  if (!window.confirm(`确认删除产品 ${row.code}？`)) return
  await remove(row.code)
}

function openForm(row?: any) {
  formError.value = ''
  form.mode = row?.code ? 'edit' : 'create'
  form.code = row?.code || ''
  form.name = row?.name || ''
  formOpen.value = true
}

onMounted(load)
</script>

<style scoped>
.material-products { margin-bottom: 12px; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
h3 { font-size: 16px; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
.toolbar { display: flex; gap: 10px; align-items: end; flex-wrap: wrap; margin: 12px 0; }
.toolbar label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; min-width: 220px; }
.mini { color: var(--muted); font-size: 11px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; }
th { color: var(--muted); font-weight: 600; }
tbody tr.editable { cursor: pointer; }
tbody tr.editable:hover td { background: var(--tech-blue-soft); }
.link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; padding: 0 6px 0 0; font-family: inherit; font-size: 11px; }
.danger-link { color: var(--red); }
.empty { text-align: center; color: var(--muted); }
.modal-mask { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(4,8,18,.65); }
.modal { width: 100%; max-width: 760px; max-height: 92dvh; overflow: auto; background: var(--white); border-radius: 10px; padding: 18px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; margin-top: 12px; }
.single-grid { grid-template-columns: 1fr; }
.form-grid label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.full { grid-column: 1 / -1; }
input, select, textarea { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 7px 8px; font-family: inherit; color: var(--ink); background: var(--white); }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.msg { padding: 9px 12px; border-radius: 5px; margin-bottom: 10px; }
.msg.err { background: var(--red-soft); color: var(--red); }
.msg.ok { background: var(--green-soft); color: var(--green); }
@media (max-width: 700px) { .panel-head { flex-direction: column; } .form-grid { grid-template-columns: 1fr; } .full { grid-column: auto; } }
</style>
