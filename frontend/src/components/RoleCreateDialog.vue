<template>
  <Teleport to="body">
    <Transition name="role-dialog">
      <div v-if="open" class="role-dialog-mask" @click.self="requestClose">
        <div
          ref="dialogRef"
          class="role-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="role-dialog-title"
          tabindex="-1"
        >
          <div class="dialog-head">
            <h3 id="role-dialog-title">创建角色</h3>
            <button class="dialog-close" type="button" aria-label="关闭创建角色弹窗" :disabled="submitting" @click="requestClose">✕</button>
          </div>
          <div v-if="closeNotice" class="msg err" role="alert">{{ closeNotice }}</div>
          <div class="dialog-body">
            <RoleCombinationForm
              show-cancel
              @cancel="requestClose"
              @created="emit('created', $event)"
            />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import RoleCombinationForm from './RoleCombinationForm.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean]; created: [value: any] }>()

const router = useRouter()
const dialogRef = ref<HTMLElement | null>(null)
const submitting = ref(false)
const closeNotice = ref('')
let previousFocus: HTMLElement | null = null
let previousOverflow = ''
let listenerBound = false

function focusableElements(): HTMLElement[] {
  const root = dialogRef.value
  if (!root) return []
  return Array.from(root.querySelectorAll<HTMLElement>(
    'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
  )).filter(el => el.offsetParent !== null || el === document.activeElement)
}

function onKeydown(event: KeyboardEvent) {
  if (!props.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    requestClose()
    return
  }
  if (event.key !== 'Tab') return
  const items = focusableElements()
  if (!items.length) {
    event.preventDefault()
    dialogRef.value?.focus()
    return
  }
  const first = items[0]
  const last = items[items.length - 1]
  const active = document.activeElement as HTMLElement | null
  if (event.shiftKey && (active === first || active === dialogRef.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

function bind() {
  if (listenerBound) return
  document.addEventListener('keydown', onKeydown, true)
  listenerBound = true
}

function unbind() {
  if (!listenerBound) return
  document.removeEventListener('keydown', onKeydown, true)
  listenerBound = false
}

function requestClose() {
  if (submitting.value) {
    closeNotice.value = '角色创建中，请等待提交完成后再关闭。'
    return
  }
  emit('update:open', false)
}

function cleanup() {
  unbind()
  document.body.style.overflow = previousOverflow
  if (previousFocus && document.contains(previousFocus)) previousFocus.focus()
  previousFocus = null
}

watch(() => props.open, async (open) => {
  closeNotice.value = ''
  if (open) {
    previousFocus = document.activeElement as HTMLElement | null
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    bind()
    await nextTick()
    const first = dialogRef.value?.querySelector<HTMLElement>('#combo-role-name')
      || focusableElements()[0]
    if (first) first.focus()
    else dialogRef.value?.focus()
  } else {
    cleanup()
  }
}, { immediate: true })

onBeforeUnmount(cleanup)
</script>

<style scoped>
.role-dialog-mask {
  position: fixed; inset: 0; z-index: 2000; display: flex; align-items: center; justify-content: center;
  padding: 20px; background: rgba(12,18,28,.52); backdrop-filter: blur(2px);
}
.role-dialog {
  width: min(620px, 100%); max-height: min(88vh, 860px); display: flex; flex-direction: column;
  background: var(--white); border: 1px solid var(--line); border-radius: 14px;
  box-shadow: 0 24px 80px rgba(0,0,0,.24); overflow: hidden; outline: none;
}
.dialog-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 16px 18px; border-bottom: 1px solid var(--line); background: var(--white);
}
.dialog-head h3 { font-size: 18px; }
.dialog-close {
  width: 30px; height: 30px; display: grid; place-items: center; border: 1px solid var(--line);
  border-radius: 7px; background: var(--white); color: var(--muted); cursor: pointer;
}
.dialog-close:hover:not(:disabled), .dialog-close:focus-visible { color: var(--red); border-color: var(--red); outline: none; }
.dialog-close:disabled { opacity: .45; cursor: not-allowed; }
.dialog-body { padding: 16px 18px 20px; overflow: auto; overscroll-behavior: contain; }
.msg { padding: 8px 10px; margin: 0 18px 8px; border-radius: 6px; font-size: 12px; }
.role-dialog-enter-active, .role-dialog-leave-active { transition: opacity .18s ease; }
.role-dialog-enter-active .role-dialog, .role-dialog-leave-active .role-dialog { transition: transform .18s ease, opacity .18s ease; }
.role-dialog-enter-from, .role-dialog-leave-to { opacity: 0; }
.role-dialog-enter-from .role-dialog, .role-dialog-leave-to .role-dialog { transform: translateY(10px) scale(.985); opacity: 0; }
@media (prefers-reduced-motion: reduce) {
  .role-dialog-enter-active, .role-dialog-leave-active,
  .role-dialog-enter-active .role-dialog, .role-dialog-leave-active .role-dialog { transition: none; }
}
@media (max-width: 768px) {
  .role-dialog-mask { align-items: flex-end; padding: 0; }
  .role-dialog { width: 100%; max-height: 92vh; border-radius: 14px 14px 0 0; }
}
</style>
