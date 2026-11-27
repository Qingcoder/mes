import { get, post, badge, fmt, toast, openModal, closeModal } from './api.js';

const STATUS = ['idle', 'running', 'down', 'maintenance'];

export async function render(root) {
  const eqs = await get('/equipment');
  const cards = eqs.map((e) => `<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center"><h3>${e.name}</h3>${badge(e.status)}</div>
    <div class="mini mono">${e.code}</div>
    <div class="kv" style="margin-top:12px"><div>当前工单：${e.current_order_id || '-'}</div><div>当前工序：${e.current_operation_id || '-'}</div><div>更新：${fmt(e.updated_at)}</div></div>
    <div class="toolbar" style="margin-top:14px"><button class="btn sm" data-act="status" data-id="${e.id}">变更状态</button><button class="btn sm" data-act="events" data-id="${e.id}">状态日志</button></div>
  </div>`).join('') || '<div class="card empty">暂无设备，可通过 API 创建</div>';

  root.innerHTML = `<h2>设备状态监控</h2><div class="sub">设备状态由工序开工/完工自动联动，也可人工调整；每次变更写入状态日志</div>
    <div class="toolbar">${STATUS.map((s) => `<span class="badge ${s}">${s}: ${eqs.filter((e) => e.status === s).length}</span>`).join(' ')}</div>
    <div class="grid g3">${cards}</div>`;

  root.onclick = async (e) => {
    const btn = e.target.closest('button[data-act]');
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const eq = eqs.find((x) => x.id === id);
    try {
      if (btn.dataset.act === 'status') openStatus(eq);
      else await showEvents(id, eq.name);
    } catch (err) { toast(err.message, 'err'); }
  };

  async function refreshSelf() { await render(document.getElementById('app')); }

  function openStatus(eq) {
    openModal(`<h3>变更设备状态 · ${eq.name}</h3>
      <div class="field"><label>状态</label><select id="f_status">${STATUS.map((s) => `<option value="${s}"${s === eq.status ? ' selected' : ''}>${s}</option>`).join('')}</select></div>
      <div class="field"><label>原因</label><input id="f_reason" placeholder="如：计划保养 / 设备故障"></div>
      <div class="modal-foot"><button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="f_save">保存</button></div>`);
    document.getElementById('f_save').onclick = async () => {
      try {
        await post(`/equipment/${eq.id}/status`, { status: document.getElementById('f_status').value, reason: document.getElementById('f_reason').value });
        closeModal(); toast('设备状态已更新'); await refreshSelf();
      } catch (err) { toast(err.message, 'err'); }
    };
  }

  async function showEvents(id, name) {
    const events = await get(`/equipment/${id}/events`);
    const rows = events.map((v) => `<tr><td class="mini">${fmt(v.at)}</td><td>${v.from_status || '-'} → ${badge(v.to_status)}</td><td class="mini">${v.reason || ''}</td></tr>`).join('') || '<tr><td colspan="3" class="empty">暂无日志</td></tr>';
    openModal(`<h3>状态日志 · ${name}</h3><table><thead><tr><th>时间</th><th>变更</th><th>原因</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="modal-foot"><button class="btn" onclick="closeModal()">关闭</button></div>`, true);
  }
}
