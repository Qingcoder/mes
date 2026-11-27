# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\daqing.yao\browser-kit')
from web_auto import WebAuto

SHOT = r'C:\Users\daqing.yao\Desktop\daimon-mes\docs\_polish_check.png'
with WebAuto(headless=True) as w:
    page = w._page
    page.set_viewport_size({"width": 1440, "height": 900})
    w.open('http://127.0.0.1:8007/login')
    w.wait(500)
    w.type('input[placeholder="请输入密码"]', '123456')
    w.click('button[type="submit"]')
    w.wait(1500)

    print('URL:', page.url)
    crumb = page.eval_on_selector('.crumb', 'el => el.textContent.replace(/\\s+/g," ").trim()')
    kpis = page.eval_on_selector_all('.kpi-label', 'els => els.map(e => e.textContent.trim())')
    dashbar = page.eval_on_selector('.dash-bar', 'el => el.textContent.replace(/\\s+/g," ").trim()')
    print('CRUMB:', crumb)
    print('KPI_LABELS:', kpis)
    print('DASH_BAR:', dashbar)
    w.screenshot(SHOT)

    # 导航到工单，面包屑应更新
    w.click('.nav-link:has-text("工单")')
    w.wait(600)
    crumb2 = page.eval_on_selector('.crumb', 'el => el.textContent.replace(/\\s+/g," ").trim()')
    print('CRUMB_AFTER_NAV:', crumb2)
    print('SHOT:', SHOT)
