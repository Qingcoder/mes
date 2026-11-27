import { get, post, badge, fmt, toast, openModal, closeModal } from './api.js';

let cache = { orders: [], products: [], routes: [] };

export async function render(root) {
  const [orders, products, routes] = await Promise.all([get('/orders'), get('/products'), get('/routes')]);
  cache = { orders, products, routes };
  const pname = Object.fromEntries(products.map((p) => [p.id, p.name]));
  const rname = Object.fromEntries(routes.map((r) => [r.id, `${r.name} · ${r.version}`]));

  const rows = orders.map((o) => {
    const done = o.operations.filter((x) => x.status === 'done').length;
    const active = o.status === 'released' || o.status === 'in_progress';
    return `<tr><td class="mono"><b>${o.order_no}</b></td><td>${pname[o.product_id] || '-'}<div class="mini">${rname[o.route_id] || ''}</div></td>
      <td>${o.plan_qty}</td><td>${badge(o.status)}</td><td>${done}/${o.operations.length}</td>
      <td class="mini">${fmt(o.created_at)}</td><td style="white-space:nowrap">
        ${o.status === 'draft' ? `<button class="btn sm primary" data-act="release" data-id="${o.id}">下发</button>` : ''}
        ${active ? `<button class="btn sm" data-act="report" data-id="${o.id}">报工</button>` : ''}
        <button class="btn sm" data-act="detail" data-id="${o.id}">详情</button>
      </td></tr>`;
  }).join('') || '<tr><td colspan="7" class="empty">暂无工单，点击右上角创建</td></tr>';

  root.innerHTML = `
    <h2>生产订单管理</h2><div class="sub">订单按工艺路线展开工序；下发后进入执行，报工驱动工序流转</div>
    <div class="toolbar"><button class="btn primary" data-act="new">+ 新建生产订单</button><span class="mini">共 ${orders.length} 张工单</span></div>
    <div class="card"><table><thead><tr><th>工单号</th><th>产品 / 工艺</th><th>计划数</th><th>状态</th><th>工序完成</th><th>创建时间</th><th style="text-align:right">操作</th></tr></thead><tbody>${rows}</tbody></table></div>`;

  root.onclick = async (e) => {
    const btn = e.target.closest('button[data-act]');
    if (!btn) return;
    const act = btn.dataset.act;
    const id = Number(btn.dataset.id);
    const order = cache.orders.find((o) => o.id === id);
    try {
      if (act === 'new') openNew();
      else if (act === 'release') { await post(`/orders/${id}/release`); toast('工单已下发，首工序开工'); await render(root); }
      else if (act === 'report') openReport(order);
      else if (act === 'detail') openDetail(order);
    } catch (err) { toast(err.message, 'err'); }
  };
}

function openNew() {
  const products = cache.products.map((p) => `<option value="${p.id}">${p.name}</option>`).join('');
  const routes = cache.routes.map((r) => `<option value="${r.id}">${r.name} · ${r.version}</option>`).join('');
  openModal(`<h3>新建生产订单</h3>
    <div class="field"><label>产品</label><select id="f_product">${products}</select></div>
    <div class="field"><label>工艺路线</label><select id="f_route">${routes}</select></div>
    <div class="field"><label>计划数量</label><input id="f_qty" type="number" min="1" value="20"></div>
    <div class="field"><label>工单号（留空自动生成）</label><input id="f_no" placeholder="WO-..." ></div>
    <div class="modal-foot"><button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="f_save">创建</button></div>`);
  document.getElementById('f_save').onclick = async () => {
    const body = {
      product_id: Number(document.getElementById('f_product').value),
      route_id: Number(document.getElementById('f_route').value),
      plan_qty: Number(document.getElementById('f_qty').value),
    };
    const no = document.getElementById('f_no').value.trim();
    if (no) body.order_no = no;
    try { await post('/orders', body); closeModal(); toast('工单已创建，状态为草稿'); await render(document.getElementById('app')); }
    catch (err) { toast(err.message, 'err'); }
  };
}

function openReport(order) {
  const op = order.operations.find((x) => x.status === 'in_progress');
  if (!op) { toast('当前没有进行中的工序', 'err'); return; }
  openModal(`<h3>工序报工 · ${order.order_no}</h3>
    <p class="sub">当前工序：${op.seq} ${op.name}　计划 ${op.plan_qty}　已报 ${op.good_qty + op.bad_qty}</p>
    <div class="grid g2">
      <div class="field"><label>合格数量</label><input id="f_good" type="number" min="0" value="${Math.max(0, op.plan_qty - op.good_qty - op.bad_qty)}"></div>
      <div class="field"><label>不合格数量</label><input id="f_bad" type="number" min="0" value="0"></div>
    </div>
    <div class="field"><label>操作人</label><input id="f_op" placeholder="如：张作业"></div>
    <div class="field"><label>备注</label><textarea id="f_note" placeholder="停机原因、异常说明等"></textarea></div>
    <div class="modal-foot"><button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="f_save">提交报工</button></div>`);
  document.getElementById('f_save').onclick = async () => {
    const body = {
      good_qty: Number(document.getElementById('f_good').value),
      bad_qty: Number(document.getElementById('f_bad').value),
      operator: document.getElementById('f_op').value,
      note: document.getElementById('f_note').value,
    };
    try {
      const res = await post(`/orders/${order.id}/report`, body);
      closeModal(); toast('报工成功 · ' + res.transition); await render(document.getElementById('app'));
    } catch (err) { toast(err.message, 'err'); }
  };
}

function openDetail(order) {
  const steps = order.operations.map((op) => `<div class="step ${op.status}"><b>${op.seq}. ${op.name}</b> ${badge(op.status)}
    <div class="mini">计划 ${op.plan_qty} · 合格 ${op.good_qty} · 不良 ${op.bad_qty} · 开始 ${fmt(op.started_at)} · 完成 ${fmt(op.finished_at)}</div></div>`).join('');
  const recs = order.records.map((r) => `<tr><td class="mini">${fmt(r.recorded_at)}</td><td>${r.operator || '-'}</td><td>${r.good_qty}</td><td>${r.bad_qty}</td><td class="mini">${r.note || ''}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">暂无报工记录</td></tr>';
  openModal(`<h3>工单详情 · ${order.order_no}</h3>
    <div class="kv"><div>状态：${badge(order.status)}</div><div>计划数量：${order.plan_qty}</div><div>创建：${fmt(order.created_at)}</div><div>完工：${fmt(order.completed_at)}</div></div>
    <h3 style="margin-top:16px">工序流程</h3><div class="timeline">${steps}</div>
    <h3 style="margin-top:10px">报工记录</h3><table><thead><tr><th>时间</th><th>操作人</th><th>合格</th><th>不良</th><th>备注</th></tr></thead><tbody>${recs}</tbody></table>
    <div class="modal-foot"><button class="btn" onclick="closeModal()">关闭</button></div>`, true);
}
