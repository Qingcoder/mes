import { onMounted, onUnmounted, ref } from 'vue'

const COMPACT_QUERY = '(max-width: 768px)'
const COARSE_QUERY = '(pointer: coarse)'

function matches(query: string): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia(query).matches
}

function isDesktopMode(): boolean {
  return !matches(COMPACT_QUERY) && !matches(COARSE_QUERY)
}

export function useDesktopMode() {
  const isDesktop = ref(isDesktopMode())
  let compactMq: MediaQueryList | null = null
  let coarseMq: MediaQueryList | null = null
  const update = () => { isDesktop.value = isDesktopMode() }

  function listen(mq: MediaQueryList | null) {
    if (!mq) return
    if (mq.addEventListener) mq.addEventListener('change', update)
    else mq.addListener(update)
  }
  function unlisten(mq: MediaQueryList | null) {
    if (!mq) return
    if (mq.removeEventListener) mq.removeEventListener('change', update)
    else mq.removeListener(update)
  }

  onMounted(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      compactMq = window.matchMedia(COMPACT_QUERY)
      coarseMq = window.matchMedia(COARSE_QUERY)
      listen(compactMq)
      listen(coarseMq)
    }
    update()
  })
  onUnmounted(() => {
    unlisten(compactMq)
    unlisten(coarseMq)
  })

  return { isDesktop }
}
