<template>
  <div class="grid g2">
    <div class="card">
      <h2>包装出库</h2>
      <p class="sub">所有 SN 必须通过最后一站才允许装箱</p>
      <div class="field"><label>箱号</label><input v-model="boxNo" class="mono" placeholder="BOX-001" /></div>
      <div class="field"><label>本箱 SN（每行一个，或逗号分隔）</label><textarea v-model="snText" rows="10" class="mono" placeholder="DAP93226AS00019D&#10;DAP93226AS000294"></textarea></div>
      <div class="toolbar">
        <button class="btn sm" @click="downloadSnTemplate">下载导入模板</button>
        <label class="btn sm file-btn">选择表格文件<input type="file" accept=".xlsx,.xls,.csv,.txt" @change="onSnFile" /></label>
      </div>
      <div v-if="fileName" class="mini">已读取：{{ fileName }}（{{ parsedCount }} 条）</div>
      <div v-if="importError" class="msg err">{{ importError }}</div>
      <div class="field"><label>操作人</label><input v-model="operator" placeholder="op01" /></div>
      <button class="btn primary" @click="submit" :disabled="!boxNo || !snText.trim()">封箱出库</button>
      <div v-if="msg" :class="['msg', ok ? 'ok' : 'err']" style="margin-top:16px">{{ msg }}</div>
    </div>
    <div class="card">
      <h2>装箱规则</h2>
      <ul style="line-height:2;margin-left:20px;color:var(--gray)">
        <li>配比在建单时自定义（N 台/箱），不写死产品类型</li>
        <li>一箱只能装同一工单的 SN</li>
        <li>未通过全部站点的 SN 会被拒绝</li>
        <li>封箱后生成箱号，可在「数据查询」按箱号反查</li>
      </ul>
      <div class="msg ok" v-if="lastBox">
        已封箱：<b class="mono">{{ lastBox.box_no }}</b> · {{ lastBox.qty }} 台
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { dedupe, downloadSnTemplate, normalizeSns, parseSnFile, validateSns } from '../utils/import'

const route = useRoute()
const boxNo = ref(''); const snText = ref(''); const operator = ref('op01')
const msg = ref(''); const ok = ref(true); const lastBox = ref<any>(null)
const fileName = ref(''); const parsedCount = ref(0); const importError = ref('')
onMounted(() => { if (route.query.box) boxNo.value = String(route.query.box) })
function setImportError(text: string) { importError.value = text; msg.value = '' }
function checkSns(values: string[]): string[] | null {
  const unique = dedupe(values)
  const { valid, invalid } = validateSns(unique)
  if (invalid.length) {
    const preview = invalid.slice(0, 5).join('、')
    const more = invalid.length > 5 ? ` 等 ${invalid.length} 条` : ''
    setImportError(`SN 格式错误：${preview}${more}；要求 16 位大写字母或数字`)
    return null
  }
  return valid
}
async function onSnFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const result = await parseSnFile(file)
  if (result.errorMessage) { setImportError(result.errorMessage); input.value = ''; return }
  const checked = checkSns(result.values)
  if (!checked) { input.value = ''; return }
  snText.value = checked.join('\n'); fileName.value = file.name; parsedCount.value = checked.length
  msg.value = `已从文件解析 ${checked.length} 条 SN`; ok.value = true; importError.value = ''
  input.value = ''
}
async function submit() {
  const sns = checkSns(normalizeSns(snText.value))
  if (!sns?.length) return
  try {
    const r = await api.pack({ box_no: boxNo.value.trim(), sns, operator: operator.value })
    lastBox.value = r; msg.value = `封箱成功：${r.box_no}（${r.qty} 台）`; ok.value = true; importError.value = ''
    boxNo.value = ''; snText.value = ''; fileName.value = ''; parsedCount.value = 0
  } catch (e: any) { msg.value = e.message; ok.value = false }
}
</script>

<style scoped>
.file-btn { position: relative; overflow: hidden; display: inline-flex; align-items: center }
.file-btn input { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100% }
</style>
