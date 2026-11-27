import { get } from './api.js';
import { render as renderDashboard } from './dashboard.js';
import { render as renderOrders } from './orders.js';
import { render as renderOperations } from './operations.js';
import { render as renderEquipment } from './equipment.js';
import { render as renderRecords } from './records.js';

const pages = {
  dashboard: renderDashboard,
  orders: renderOrders,
  operations: renderOperations,
  equipment: renderEquipment,
  records: renderRecords,
};

let current = 'dashboard';

export async function showPage(page) {
  if (!pages[page]) page = 'dashboard';
  current = page;
  document.querySelectorAll('#nav button').forEach((b) => b.classList.toggle('active', b.dataset.page === page));
  document.getElementById('app').innerHTML = '<div class="loading">加载中…</div>';
  try {
    await pages[page](document.getElementById('app'));
  } catch (err) {
    document.getElementById('app').innerHTML = `<div class="card"><h3>加载失败</h3><p class="mini">${err.message}</p></div>`;
  }
}

document.getElementById('nav').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-page]');
  if (btn) showPage(btn.dataset.page);
});

setInterval(() => {
  const el = document.getElementById('clock');
  if (el) el.textContent = new Date().toLocaleString('zh-CN', { hour12: false });
}, 1000);

showPage('dashboard');
