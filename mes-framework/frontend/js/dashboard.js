import { get, badge, fmt } from './api.js';

export async function render(root) {
  const [d, orders, products] = await Promise.all([get('/dashboard'), get('/orders'), get('/products')]);
  const pname = Object.fromEntries(products.map((p) => [p.id, p.name]));
  const ono = Object.fromEntries(orders.map((o) => [o.id, o.order_no]));
  const kpi = (lab, val, foot, color) => `<div class="card kpi"><div class="lab">${lab}</div><div class="val" style="color:${color}">${val}</div><div class="foot">${foot}</div></div>`;

  const rows = orders.map((o) => {
    const done = o.operations.filter((x) => x.status === 'done').length;
    const pct = Math.round(done / (o.operations.length || 1) * 100);
    return `<tr><td class="mono">${o.order_no}</td><td>${pname[o.product_id] || '-'}</td><td>${o.plan_qty}</td><td>${badge(o.status)}</td><td>${done}/${o.operations.length}<div class="progress"><i style="width:${pct}%"></i></div></td><td class="mini">${fmt(o.released_at || o.created_at)}</td></tr>`;
  }).join('') || '<tr><td colspan="6" class="empty">暂无工单</td></tr>';

  const recs = d.recent_records.map((r) => `<tr><td class="mini">${fmt(r.recorded_at)}</td><td class="mono">${ono[r.work_order_id] || r.work_order_id}</td><td>${r.operator || '-'}</td><td style="color:var(--green)">${r.good_qty}</td><td style="color:var(--red)">${r.bad_qty}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">暂无报工记录</td></tr>';

  root.innerHTML = `
    <h2>生产看板</h2><div class="sub">订单、工序、设备与生产数据的实时汇总</div>
    <div class="grid g4" style="margin-bottom:16px">
      ${kpi('工单总数', d.orders.total, `草稿 ${d.orders.by_status.draft} / 在制 ${(d.orders.by_status.released || 0) + (d.orders.by_status.in_progress || 0)}`, '#23272b')}
      ${kpi('已完工', d.orders.by_status.completed || 0, '整单完成数量', '#1a7a4c')}
      ${kpi('合格品数', d.production.good_qty, `累计报工 ${d.production.record_count} 次`, '#2b6cb0')}
      ${kpi('合格率', d.production.qualified_rate + '%', `合格 ${d.production.good_qty} / 总 ${d.production.total_qty}`, '#E61736')}
    </div>
    <div class="grid g2">
      <div class="card"><h3>工单进度</h3><table><thead><tr><th>工单</th><th>产品</th><th>计划</th><th>状态</th><th>工序</th><th>时间</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div>
        <div class="card" style="margin-bottom:16px"><h3>设备状态</h3><div class="toolbar">
          ${Object.entries(d.equipment.by_status).map(([k, v]) => `<span class="badge ${k}">${k}: ${v}</span>`).join(' ')}
        </div><p class="mini">运行中设备 ${d.equipment.by_status.running || 0} / ${d.equipment.total}，状态随工序开工/完工自动切换。</p></div>
        <div class="card"><h3>最近报工</h3><table><thead><tr><th>时间</th><th>工单</th><th>操作人</th><th>合格</th><th>不良</th></tr></thead><tbody>${recs}</tbody></table></div>
      </div>
    </div>`;
}
