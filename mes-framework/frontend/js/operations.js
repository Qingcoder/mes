import { get, badge, fmt } from './api.js';

export async function render(root) {
  const ops = await get('/operations');
  let filter = 'ALL';

  function draw() {
    const list = filter === 'ALL' ? ops : ops.filter((o) => o.status === filter);
    const rows = list.map((o) => `<tr><td class="mono">${o.order_no}</td><td>${o.seq}</td><td>${o.name}</td><td>${badge(o.status)}</td>
      <td>${o.good_qty + o.bad_qty}/${o.plan_qty}<div class="progress"><i style="width:${Math.min(100, Math.round((o.good_qty + o.bad_qty) / (o.plan_qty || 1) * 100))}%"></i></div></td>
      <td><span style="color:var(--green)">${o.good_qty}</span> / <span style="color:var(--red)">${o.bad_qty}</span></td>
      <td>${o.equipment_id || '-'}</td><td class="mini">${fmt(o.started_at)}</td></tr>`).join('') || '<tr><td colspan="8" class="empty">暂无工序数据</td></tr>';

    root.innerHTML = `<h2>工序流程跟踪</h2><div class="sub">工单工序实例与实时进度；点击「生产订单 → 报工」可推动当前工序</div>
      <div class="toolbar"><label>状态筛选</label><select id="f_filter">
        <option value="ALL">全部</option><option value="pending"${filter === 'pending' ? ' selected' : ''}>待执行</option>
        <option value="in_progress"${filter === 'in_progress' ? ' selected' : ''}>进行中</option><option value="done"${filter === 'done' ? ' selected' : ''}>已完成</option>
      </select><span class="mini">共 ${list.length} 条工序</span></div>
      <div class="card"><table><thead><tr><th>工单</th><th>序号</th><th>工序</th><th>状态</th><th>进度</th><th>合格/不良</th><th>设备</th><th>开工时间</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  root.onchange = (e) => { if (e.target.id === 'f_filter') { filter = e.target.value; draw(); } };
  draw();
}
