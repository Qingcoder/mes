export async function api(path, options = {}) {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (_) { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}

export const get = (path) => api(path);
export const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

export function toast(msg, type = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = '.3s'; setTimeout(() => el.remove(), 320); }, 3200);
}

export function fmt(v) {
  if (!v) return '-';
  const d = new Date(v);
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function badge(status) {
  return `<span class="badge ${status || ''}">${status || '-'}</span>`;
}

export function openModal(html, wide = false) {
  const mask = document.getElementById('modal-mask');
  const modal = document.getElementById('modal');
  modal.className = 'modal' + (wide ? ' wide' : '');
  modal.innerHTML = html;
  mask.classList.add('show');
}

export function closeModal() {
  document.getElementById('modal-mask').classList.remove('show');
}

window.closeModal = closeModal;
