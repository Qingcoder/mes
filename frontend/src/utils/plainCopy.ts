/**
 * 全局纯文本复制。
 *
 * 浏览器的“来源链接 / 引用标题 / 富文本样式”通常来自 copy 事件里写入的
 * text/html、text/rtf 等剪贴板格式；这里在捕获阶段统一清掉富文本格式，
 * 只保留 text/plain，使复制到任何目标都保持纯文本。
 */
function getPlainSelection(): string {
  const sel = typeof window !== 'undefined' ? window.getSelection() : null
  return sel ? sel.toString() : ''
}

export function installPlainTextCopy() {
  if (typeof document === 'undefined') return
  document.addEventListener('copy', (e: ClipboardEvent) => {
    const text = getPlainSelection()
    if (!text || !e.clipboardData) return
    e.preventDefault()
    e.clipboardData.clearData()
    e.clipboardData.setData('text/plain', text)
  }, true)
}
