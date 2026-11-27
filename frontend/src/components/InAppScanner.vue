<template>
  <teleport to="body">
    <div v-if="visible" class="scanner-mask" @click.self="close">
      <div class="scanner-card">
        <div class="scanner-head">
          <h3>应用内扫码</h3>
          <button class="scanner-x" title="关闭" @click="close">✕</button>
        </div>
        <div class="scanner-viewport">
          <video ref="videoEl" playsinline muted autoplay></video>
          <div class="scanner-frame"></div>
          <div class="scanner-hint">{{ hint }}</div>
        </div>
        <div v-if="error" class="scanner-error">{{ error }}</div>
        <input ref="photoInput" class="photo-input" type="file" accept="image/*" capture="environment" @change="onPhotoChange" />
        <div class="scanner-actions">
          <button v-if="flashSupported" class="btn sm" @click="toggleFlash">{{ flashEnabled ? '关闭闪光' : '开启闪光' }}</button>
          <button class="btn sm" :disabled="photoBusy" @click="pickPhoto">{{ photoBusy ? '识别中…' : '拍照识别' }}</button>
          <button class="btn sm" @click="restart">重试识别</button>
          <button class="btn sm ghost" @click="close">关闭</button>
        </div>
        <p class="scanner-foot">支持二维码与常见一维码；相机不可用时可拍照识别</p>
      </div>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { nextTick, onUnmounted, ref } from 'vue'
import { BrowserMultiFormatReader } from '@zxing/browser'

const emit = defineEmits<{
  (e: 'result', payload: { text: string; format: string }): void
  (e: 'close'): void
}>()

const visible = ref(false)
const videoEl = ref<HTMLVideoElement | null>(null)
const hint = ref('正在启动相机…')
const error = ref('')
const flashSupported = ref(false)
const flashEnabled = ref(false)
const photoInput = ref<HTMLInputElement | null>(null)
const photoBusy = ref(false)

let reader: BrowserMultiFormatReader | null = null
let controls: any = null
let stream: MediaStream | null = null
let misses = 0
let decoded = false

function completeScan(text: string, format: string) {
  if (!text) return
  try { navigator.vibrate?.(50) } catch { /* 不支持振动时忽略 */ }
  emit('result', { text, format })
  close()
}

function describeCameraError(e: any): string {
  const name = e?.name || ''
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return '相机权限被拒绝。iOS：设置 > Safari > 相机；Android：浏览器权限 > 允许相机，然后重试。'
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return '未检测到摄像头，请确认设备具备后置摄像头。'
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return '摄像头被其他应用占用，请关闭其他相机应用后重试。'
  }
  return '摄像头启动失败：' + (e?.message || '请检查浏览器权限')
}

async function start() {
  error.value = ''
  hint.value = '正在启动相机…'
  misses = 0
  decoded = false
  if (!window.isSecureContext) {
    error.value = '当前页面不是 HTTPS，iPhone 相机扫码会受限；请点击下方“拍照识别”使用系统相机。'
    return
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    error.value = '当前浏览器不支持应用内相机扫码，请点击“拍照识别”使用系统相机。'
    return
  }
  try {
    reader = new BrowserMultiFormatReader()
    await nextTick()
    if (!videoEl.value) return
    const constraints: MediaStreamConstraints = {
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: 1280 },
        height: { ideal: 720 },
        advanced: [{ focusMode: 'continuous' } as any],
      },
      audio: false,
    }
    controls = await reader.decodeFromConstraints(constraints, videoEl.value, (result: any) => {
      if (decoded) return
      const text = result?.getText?.()
      if (text) {
        decoded = true
        completeScan(String(text).trim(), String(result.getBarcodeFormat?.() || 'BARCODE'))
        return
      }
      misses++
      if (misses === 25) hint.value = '识别困难：请对准条码、保持画面稳定，或开启闪光灯'
      if (misses === 60) hint.value = '弱光 / 模糊：请增加环境光线后重试'
    })
    stream = videoEl.value.srcObject as MediaStream | null
    const track: any = stream?.getVideoTracks?.()[0]
    flashSupported.value = !!track?.getCapabilities?.()?.torch
    if (track?.getCapabilities?.()?.focusMode?.includes?.('continuous')) {
      await track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] })
    }
    hint.value = '自动对焦中，请将二维码 / 条码放入框内'
  } catch (e: any) {
    error.value = describeCameraError(e)
    stop()
  }
}

function pickPhoto() {
  if (photoBusy.value) return
  photoInput.value?.click()
}

async function onPhotoChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  error.value = ''
  hint.value = '正在识别图片…'
  photoBusy.value = true
  const url = URL.createObjectURL(file)
  try {
    const decoder = new BrowserMultiFormatReader()
    const result: any = await decoder.decodeFromImageUrl(url)
    const text = result?.getText?.()
    if (!text) throw new Error('未识别到条码')
    completeScan(String(text).trim(), String(result.getBarcodeFormat?.() || 'BARCODE'))
  } catch {
    error.value = '图片中未识别到可用条码，请对准条码重新拍照，或使用相机实时扫描。'
    hint.value = '可重新拍照识别'
  } finally {
    URL.revokeObjectURL(url)
    input.value = ''
    photoBusy.value = false
    if (visible.value && !error.value) hint.value = '自动对焦中，请将二维码 / 条码放入框内'
  }
}

function stop() {
  controls?.stop?.(); controls = null
  reader = null
  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null }
  if (videoEl.value) videoEl.value.srcObject = null
  flashSupported.value = false; flashEnabled.value = false
}

function open() {
  visible.value = true
  void start()
}

function close() {
  stop()
  visible.value = false
  emit('close')
}

function restart() {
  stop()
  void start()
}

async function toggleFlash() {
  const track: any = stream?.getVideoTracks?.()[0]
  if (!track?.getCapabilities?.()?.torch) { error.value = '当前设备或浏览器不支持闪光灯控制'; return }
  try {
    await track.applyConstraints({ advanced: [{ torch: !flashEnabled.value }] })
    flashEnabled.value = !flashEnabled.value
    hint.value = flashEnabled.value ? '闪光灯已开启' : '闪光灯已关闭'
  } catch { error.value = '闪光灯控制失败，请手动增加环境光线' }
}

defineExpose({ open, close })
onUnmounted(stop)
</script>

<style scoped>
.scanner-mask { position: fixed; inset: 0; z-index: 2000; background: rgba(4,8,18,.72); display: flex; align-items: center; justify-content: center; padding: 18px; }
.scanner-card { width: 100%; max-width: 420px; max-height: min(92dvh, 720px); overflow: auto; background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 24px 70px rgba(0,0,0,.45); }
.scanner-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.scanner-head h3 { margin: 0; font-size: 17px; color: var(--ink); }
.scanner-x { border: 0; background: transparent; color: var(--muted); font-size: 16px; cursor: pointer; }
.scanner-viewport { position: relative; border-radius: 10px; overflow: hidden; background: #000; }
.scanner-viewport video { display: block; width: 100%; height: clamp(180px, 38dvh, 260px); object-fit: cover; }
.scanner-frame { position: absolute; inset: 34px 26px; border: 2px solid rgba(255,255,255,.8); border-radius: 10px; box-shadow: 0 0 0 9999px rgba(0,0,0,.16); pointer-events: none; }
.scanner-hint { position: absolute; left: 12px; right: 12px; bottom: 10px; text-align: center; color: #fff; font-size: 12px; text-shadow: 0 1px 5px #000; pointer-events: none; }
.scanner-error { margin-top: 10px; padding: 9px 10px; border-radius: 6px; background: var(--red-soft); color: var(--red); font-size: 12px; line-height: 1.6; }
.photo-input { display: none; }
.scanner-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.scanner-foot { margin: 10px 0 0; text-align: center; color: var(--muted); font-size: 11px; }
</style>
