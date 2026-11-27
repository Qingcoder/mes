const VOICE_KEY = 'mes_voice_enabled'

export function getVoiceEnabled(): boolean {
  try { return localStorage.getItem(VOICE_KEY) !== '0' } catch { return true }
}

export function setVoiceEnabled(enabled: boolean) {
  try { localStorage.setItem(VOICE_KEY, enabled ? '1' : '0') } catch { /* 忽略隐私模式限制 */ }
}

function voiceSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window
}

function isStationPage(): boolean {
  if (typeof window === 'undefined') return false
  return window.location.pathname === '/station' || window.location.pathname.startsWith('/station/')
}

export function speak(text: string) {
  if (!text || !getVoiceEnabled() || !voiceSupported() || !isStationPage()) return
  try {
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    u.rate = 1.05
    u.pitch = 1
    u.volume = 1
    window.speechSynthesis.speak(u)
  } catch { /* 语音不可用时静默降级 */ }
}

export function stopSpeak() {
  if (!voiceSupported()) return
  try { window.speechSynthesis.cancel() } catch { /* 忽略 */ }
}
