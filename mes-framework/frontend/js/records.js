import { get, fmt } from './api.js';

export async function render(root) {
  const [records, orders, eqs] = await Promise.all([get('/records'), get('/orders'), get('/equipment')]);
  const ono = Object.fromEntries(orders.map((o) => [o.id, o.order_no]));
  const ename = Object.fromEntries(eqs.map((e) => [e.id, e.name]));
  let fOrder = 'ALL', fEq = 'ALL';

  function draw() {
    const list = records.filter((r) => (fOrder === 'ALL' || String(r.work_order_id) === fOrder) && (fEq === 'ALL' || String(r.equipment_id || '') === fEq));
    const rows = list.map((r) => `<tr><td class="mini">${fmt(r.recorded_at)}</td><td class="mono">${ono[r.work_order_id] || r.work_order_id}</td><td>${r.operation_id}</td>
      <td>${ename[r.equipment_id] || '-'}</td><td>${r.operator || '-'}</td><td style="color:var(--green)">${r.good_qty}</td><td style="color:var(--red)">${r.bad_qty}</td><td class="mini">${r.note || ''}</td></tr>`).join('') || '<tr><td colspan="8" class="empty">暂无采集数据</td></tr>';
    const good = list.reduce((s, r) => s + r.good_qty, 0);
    const bad = list.reduce((s, r) => s + r.bad_qty, 0);

    root.innerHTML = `<h2>生产数据采集</h2><div class="sub">每次工序报工生成一条不可变记录，支持按工单与设备追溯</div>
      <div class="toolbar"><label>工单</label><select id="f_order"><option value="ALL">全部</option>${orders.map((o) => `<option value="${o.id}"${fOrder === String(o.id) ? ' selected' : ''}>${o.order_no}</option>`).join('')}</select>
      <label>设备</label><select id="f_eq"><option value="ALL">全部</option>${eqs.map((e) => `<option value="${e.id}"${fEq === String(e.id) ? ' selected' : ''}>${e.name}</option>`).join('')}</select>
      <span class="mini">${list.length} 条 · 合格 ${good} / 不良 ${bad}</span></div>
      <div class="card"><table><thead><tr><th>时间</th><th>工单</th><th>工序ID</th><th>设备</th><th>操作人</th><th>合格</th><th>不良</th><th>备注</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  root.onchange = (e) => {
    if (e.target.id === 'f_order') fOrder = e.target.value;
    if (e.target.id === 'f_eq') fEq = e.target.value;
    draw();
  };
  draw();
}
