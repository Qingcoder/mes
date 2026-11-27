<template>
  <section class="resumable-uploader">
    <div
      class="drop-zone"
      :class="{ active: dragActive, disabled: disabled }"
      role="button"
      tabindex="0"
      :aria-disabled="disabled"
      @click="openPicker"
      @keydown.enter.prevent="openPicker"
      @keydown.space.prevent="openPicker"
      @dragover.prevent="onDragOver"
      @dragenter.prevent="onDragOver"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
    >
      <div class="drop-main">
        <span class="drop-icon">⇪</span>
        <div class="drop-copy">
          <b>{{ dragActive ? '松开鼠标即可上传' : label }}</b>
          <small>{{ hint }}</small>
        </div>
      </div>
      <button class="pick-btn" type="button" :disabled="disabled" @click.stop="openPicker">选择文件</button>
      <input ref="inputRef" class="native-file-input" type="file" :accept="accept" :multiple="maxFiles > 1" @change="onInputChange" />
    </div>

    <div v-if="items.length" class="upload-list">
      <article v-for="item in items" :key="item.key" class="upload-item">
        <div class="upload-head">
          <span class="file-name" :title="item.name">{{ item.name }}</span>
          <span class="upload-size">{{ formatSize(item.size) }}</span>
          <span class="status-tag" :class="'is-' + item.status">{{ statusText(item) }}</span>
        </div>
        <div class="progress-track"><div class="progress-fill" :style="{ width: item.progress + '%' }"></div></div>
        <div class="upload-meta">
          <span>{{ formatSize(item.uploaded) }} / {{ formatSize(item.size) }} · {{ item.progress }}%</span>
          <span class="row">
            <button v-if="item.status === 'error' || item.status === 'paused'" class="link" type="button" @click="retry(item)">继续上传</button>
            <button v-if="item.status === 'uploading' || item.status === 'preparing' || item.status === 'paused' || item.status === 'error'" class="link danger-link" type="button" @click="cancel(item)">取消</button>
            <button v-if="item.status === 'done'" class="link" type="button" @click="removeItem(item)">清除</button>
          </span>
        </div>
        <div v-if="item.error" class="upload-error">{{ item.error }}</div>
      </article>
      <button v-if="hasResumable" class="btn sm" type="button" @click="resumeAll">全部继续</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, friendlyError } from '../api'

type UploadStatus = 'preparing' | 'uploading' | 'paused' | 'error' | 'done'
interface UploadItem {
  key: string
  sessionId: string
  fingerprint: string
  name: string
  size: number
  status: UploadStatus
  progress: number
  uploaded: number
  error: string
  prepared: any
}
interface SavedSession {
  key: string
  stationId: string
  sessionId: string
  fingerprint: string
  name: string
  size: number
  prepared: any
  updatedAt: number
}

const props = withDefaults(defineProps<{
  stationId: string
  accept?: string
  maxSize?: number
  maxFiles?: number
  label?: string
  hint?: string
  disabled?: boolean
  prepare?: (file: File) => any | Promise<any>
}>(), {
  accept: '*/*',
  maxSize: 200 * 1024 * 1024,
  maxFiles: 1,
  label: '拖拽文件到此处，或点击选择文件',
  hint: '任意文件均可上传；支持断点续传，文件最大 200MB',
  disabled: false,
  prepare: undefined,
})

const emit = defineEmits<{
  (event: 'uploaded', payload: { file: File; meta: any; prepared: any }): void
  (event: 'error', message: string): void
}>()

const CHUNK_SIZE = 1024 * 1024
const STORAGE_KEY = 'mes_resumable_uploads_v1'
const DB_NAME = 'mes_resumable_uploads'
const DB_STORE = 'files'
const inputRef = ref<HTMLInputElement | null>(null)
const dragActive = ref(false)
const items = reactive<UploadItem[]>([])
const hasResumable = computed(() => items.some(i => i.status === 'paused' || i.status === 'error'))

function formatSize(size: number) {
  if (!size) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(units.length - 1, Math.floor(Math.log(size) / Math.log(1024)))
  return `${(size / Math.pow(1024, index)).toFixed(index ? 1 : 0)} ${units[index]}`
}
function statusText(item: UploadItem) {
  return {
    preparing: '校验中', uploading: '上传中', paused: '可续传',
    error: '上传失败', done: '已完成',
  }[item.status] || item.status
}
function hash(text: string) {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return (h >>> 0).toString(16).padStart(8, '0')
}
function fileKey(file: File) {
  return `${props.stationId}|${file.name}|${file.size}|${file.lastModified || 0}`
}
function fingerprint(file: File) {
  return hash(fileKey(file))
}
function extOf(name: string) {
  const match = /\.([^.]+)$/.exec(name)
  return match ? `.${match[1].toLowerCase()}` : ''
}
function acceptList() {
  return String(props.accept).split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
}
function validateFile(file: File) {
  if (!file.size) throw new Error('文件为空，请重新选择')
  if (file.size > props.maxSize) throw new Error(`文件不能超过 ${formatSize(props.maxSize)}`)
  const allowed = acceptList()
  if (!allowed.length || allowed.includes('*/*') || allowed.includes('*')) return
  const ext = extOf(file.name)
  const matched = allowed.some(rule => rule.startsWith('.') ? rule === ext : rule.endsWith('/*') ? file.type.startsWith(rule.slice(0, -1)) : rule === file.type)
  if (!matched) throw new Error(`不支持的文件格式，允许：${allowed.join('、')}`)
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(DB_STORE)) db.createObjectStore(DB_STORE)
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('本地文件缓存不可用'))
  })
}
async function saveFile(key: string, file: File) {
  const db = await openDB()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readwrite')
    tx.objectStore(DB_STORE).put(file, key)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error || new Error('本地文件缓存失败'))
  })
  db.close()
}
async function loadFile(key: string): Promise<File | null> {
  const db = await openDB()
  const value = await new Promise<File | null>((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readonly')
    const request = tx.objectStore(DB_STORE).get(key)
    request.onsuccess = () => resolve(request.result as File || null)
    request.onerror = () => reject(request.error || new Error('本地文件读取失败'))
  })
  db.close()
  return value
}
async function deleteFile(key: string) {
  const db = await openDB()
  await new Promise<void>((resolve) => {
    const tx = db.transaction(DB_STORE, 'readwrite')
    tx.objectStore(DB_STORE).delete(key)
    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
  })
  db.close()
}
function readRecords(): SavedSession[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') } catch { return [] }
}
function writeRecords(records: SavedSession[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(records))
}
function saveRecord(record: SavedSession) {
  const records = readRecords().filter(r => r.key !== record.key)
  records.push(record)
  writeRecords(records)
}
function removeRecord(key: string) {
  writeRecords(readRecords().filter(r => r.key !== key))
}

function addItem(record: Omit<UploadItem, 'status' | 'progress' | 'uploaded' | 'error'>): UploadItem {
  const item: UploadItem = reactive({ ...record, status: 'preparing', progress: 0, uploaded: 0, error: '' })
  items.push(item)
  return item
}
function openPicker() {
  if (!props.disabled) inputRef.value?.click()
}
function onInputChange(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  void addFiles(files)
}
function onDragOver() { if (!props.disabled) dragActive.value = true }
function onDragLeave(event: DragEvent) {
  const target = event.currentTarget as HTMLElement
  if (!target.contains(event.relatedTarget as Node)) dragActive.value = false
}
function onDrop(event: DragEvent) {
  dragActive.value = false
  if (props.disabled) return
  void addFiles(Array.from(event.dataTransfer?.files || []))
}

async function addFiles(files: File[]) {
  for (const file of files) {
    if (items.filter(i => i.status !== 'done').length >= props.maxFiles) break
    const key = fileKey(file)
    if (items.some(i => i.key === key && i.status !== 'error')) continue
    const item = addItem({ key, sessionId: '', fingerprint: fingerprint(file), name: file.name, size: file.size, prepared: null })
    try {
      validateFile(file)
      if (props.prepare) item.prepared = await props.prepare(file)
      const status = await api.createUploadSession({
        stationId: props.stationId,
        name: file.name,
        contentType: file.type,
        size: file.size,
        chunkSize: CHUNK_SIZE,
        fingerprint: item.fingerprint,
      })
      item.sessionId = status.sessionId
      await saveFile(key, file)
      saveRecord({
        key, stationId: props.stationId, sessionId: status.sessionId,
        fingerprint: item.fingerprint, name: file.name, size: file.size,
        prepared: item.prepared, updatedAt: Date.now(),
      })
      await uploadItem(item, file)
    } catch (error: any) {
      item.status = 'error'
      item.error = friendlyError(error, '上传失败，请重试')
      emit('error', item.error)
    }
  }
}

async function uploadItem(item: UploadItem, file: File) {
  if (!item.sessionId) throw new Error('上传会话不存在，请重新选择文件')
  item.status = 'uploading'
  item.error = ''
  try {
    const status = await api.uploadSessionStatus(item.sessionId)
    let base = Number(status.received || 0)
    item.uploaded = base
    for (let index = Number(status.nextChunk || 0); index < Number(status.chunkCount); index++) {
      const start = index * Number(status.chunkSize)
      const end = Math.min(start + Number(status.chunkSize), file.size)
      const chunk = file.slice(start, end)
      const result = await api.uploadChunk(item.sessionId, index, chunk, (loaded) => {
        item.uploaded = base + loaded
        item.progress = Math.min(99, Math.round(item.uploaded / Math.max(1, file.size) * 100))
      })
      base = Number(result.received || 0)
      item.uploaded = base
      item.progress = Math.min(99, Math.round(base / Math.max(1, file.size) * 100))
      saveRecord({
        key: item.key, stationId: props.stationId, sessionId: item.sessionId,
        fingerprint: item.fingerprint, name: item.name, size: item.size,
        prepared: item.prepared, updatedAt: Date.now(),
      })
    }
    await finalize(item, file)
  } catch (error: any) {
    item.status = 'error'
    item.error = friendlyError(error, '上传中断，可点击继续上传')
    emit('error', item.error)
  }
}

async function finalize(item: UploadItem, file: File) {
  const meta = await api.completeUploadSession(item.sessionId)
  await deleteFile(item.key)
  removeRecord(item.key)
  item.status = 'done'
  item.progress = 100
  item.uploaded = item.size
  item.error = ''
  emit('uploaded', { file, meta, prepared: item.prepared })
}

async function retry(item: UploadItem) {
  const file = await loadFile(item.key)
  if (!file) {
    item.status = 'error'
    item.error = '本地文件已失效，请重新选择文件'
    removeRecord(item.key)
    return
  }
  if (!item.sessionId) {
    await addFiles([file])
    return
  }
  await uploadItem(item, file)
}
async function resumeAll() {
  for (const item of [...items]) {
    if (item.status === 'paused' || item.status === 'error') await retry(item)
  }
}
async function cancel(item: UploadItem) {
  if (item.sessionId) {
    try { await api.cancelUploadSession(item.sessionId) } catch { /* 本地清理仍继续 */ }
  }
  await deleteFile(item.key)
  removeRecord(item.key)
  removeItem(item)
}
function removeItem(item: UploadItem) {
  const index = items.indexOf(item)
  if (index >= 0) items.splice(index, 1)
}

async function restore() {
  const records = readRecords().filter(r => r.stationId === props.stationId)
  for (const record of records) {
    const file = await loadFile(record.key)
    if (!file) {
      removeRecord(record.key)
      continue
    }
    const item = addItem({
      key: record.key, sessionId: record.sessionId, fingerprint: record.fingerprint,
      name: record.name, size: record.size, prepared: record.prepared,
    })
    try {
      const status = await api.uploadSessionStatus(record.sessionId)
      item.status = status.complete ? 'uploading' : 'paused'
      item.uploaded = Number(status.received || 0)
      item.progress = Math.min(99, Math.round(item.uploaded / Math.max(1, item.size) * 100))
      if (status.complete) await finalize(item, file)
    } catch {
      item.status = 'error'
      item.error = '断点记录已失效，请重新选择文件'
      removeRecord(record.key)
      await deleteFile(record.key)
    }
  }
}

onMounted(() => { void restore() })
</script>

<style scoped>
.resumable-uploader { margin: 10px 0 14px; container: uploader / inline-size; }
.drop-zone {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  min-height: 72px; padding: 12px 14px; border: 1px dashed var(--line);
  border-radius: 10px; background: var(--bg); cursor: pointer;
  transition: border-color .15s, background .15s, box-shadow .15s;
}
.drop-zone:hover, .drop-zone.active { border-color: var(--tech-blue); background: var(--tech-blue-soft); box-shadow: 0 0 0 3px rgba(46,111,232,.08); }
.drop-zone.disabled { opacity: .6; cursor: not-allowed; }
.drop-main { display: flex; align-items: center; gap: 11px; min-width: 0; flex: 1 1 auto; }
.drop-icon { width: 36px; height: 36px; flex: none; display: grid; place-items: center; border-radius: 9px; background: var(--white); border: 1px solid var(--line); color: var(--tech-blue); font-size: 20px; box-shadow: 0 1px 2px rgba(0,0,0,.03); }
.native-file-input { display: none !important; }
.drop-copy { flex: 1 1 auto; min-width: 0; max-width: 100%; }
.drop-copy b { display: block; font-size: 13px; line-height: 1.45; overflow-wrap: anywhere; word-break: break-word; }
.drop-copy small { display: block; margin-top: 3px; color: var(--muted); font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; word-break: break-word; }
.pick-btn { flex: none; white-space: nowrap; border: 1px solid var(--tech-blue-line); background: var(--white); color: var(--tech-blue); border-radius: 7px; padding: 8px 14px; font-size: 12px; line-height: 1.2; font-weight: 600; cursor: pointer; font-family: inherit; }
.pick-btn:hover { background: var(--tech-blue); border-color: var(--tech-blue); color: var(--white); }
.pick-btn:disabled { opacity: .5; cursor: not-allowed; }
.upload-list { display: grid; gap: 8px; margin-top: 10px; }
.upload-item { border: 1px solid var(--line); border-radius: 8px; padding: 9px 10px; background: var(--white); }
.upload-head, .upload-meta { display: flex; justify-content: space-between; gap: 8px; align-items: center; font-size: 12px; }
.file-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 60%; }
.upload-size, .upload-meta { color: var(--muted); }
.status-tag { border-radius: 10px; padding: 2px 8px; font-size: 11px; background: var(--tech-blue-soft); color: var(--tech-blue); }
.status-tag.is-error { background: var(--red-soft); color: var(--red); }
.status-tag.is-done { background: var(--green-soft); color: var(--green); }
.status-tag.is-paused { background: #fff4d6; color: #8a6100; }
.progress-track { height: 6px; border-radius: 4px; background: var(--line); overflow: hidden; margin: 8px 0 6px; }
.progress-fill { height: 100%; background: var(--tech-blue); transition: width .12s linear; }
.upload-error { color: var(--red); font-size: 11px; margin-top: 5px; }
.link { border: 0; background: transparent; color: var(--tech-blue); cursor: pointer; font-family: inherit; font-size: 11px; padding: 0 4px; }
.danger-link { color: var(--red); }
@container uploader (max-width: 520px) {
  .drop-zone { flex-wrap: wrap; align-items: flex-start; }
  .drop-main { flex: 1 1 100%; }
  .pick-btn { width: 100%; }
  .upload-head, .upload-meta { align-items: flex-start; flex-direction: column; }
  .file-name { max-width: 100%; }
}
@media (max-width: 600px) {
  .drop-zone { padding: 11px; }
  .drop-icon { width: 32px; height: 32px; font-size: 18px; }
}
</style>
