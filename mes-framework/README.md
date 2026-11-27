# MES 基础功能框架（mes-framework）

一个**可运行、可追溯、可扩展**的 MES（制造执行系统）最小闭环框架。它把「生产订单 → 工艺路线展开工序 → 工序报工 → 设备状态联动 → 数据采集 → 看板汇总」串成完整链路，适合作为后续二次开发的底座。

## 参考资料（检索日期：2026-11-23）

| 来源 | 链接 | 本框架采纳的要点 |
|---|---|---|
| MFG Tech Hub《What Is MES? ... Order Walk-Through》 | https://mfgtechhub.com/mes/mes-introduction | MES 位于 ERP 与车间之间；订单下发、排程、物料/批次校验、过程执行、设备数据采集、质量检查、订单关闭与回传、完整追溯的 8 步工单流程 |
| IT/OT Convergentie《MES》 | https://itotconvergentie.nl/en/mes | ISA-95 / Purdue Level 3 定位；MESA-11 功能模型；工单执行、追踪、设备监控、数据采集四大核心；MES 不直接控制设备，只采集与记录 |
| CSDN《Java Web 开源 MES 系统设计：业务模型、技术架构与实施经验》 | https://blog.csdn.net/weixin_32306957/article/details/164197656 | 六大主数据 + 五大业务流；工艺路线 → 工单 → 工单工序 → 报工 → 质量/设备/看板的数据关系；报工记录作为不可变事实数据；乐观锁与追溯快照思路 |
| GitHub《Awesome Semiconductor Manufacturing Execution System》 | https://github.com/ishandutta2007/Awesome-Semiconductor-Manufacturing-Execution-System | 分层技术栈参考（ERP / MES Core / 设备连接 OPC UA、MQTT / SECS-GEM） |
| MESA International《MES Explained: A High Level Vision》(MESA-11) | 经 IT/OT Convergentie 页面引用（1997） | 11 项 MES 功能的标准参考框架 |

> 本框架不复制上述系统的代码，只按其公开的业务模型与架构原则做原创实现。

## 架构设计思路

```
┌─────────────────────────────────────────────┐
│ 表示层  Frontend (原生 ES Modules，零构建)   │
│ 看板 / 订单 / 工序跟踪 / 设备监控 / 数据采集  │
└───────────────┬─────────────────────────────┘
                │ HTTP/JSON
┌───────────────▼─────────────────────────────┐
│ API 层  FastAPI Routers                     │
│ /api/master  /api/orders  /api/equipment    │
│ /api/records  /api/dashboard                │
└───────────────┬─────────────────────────────┘
                │ 业务规则（状态机）
┌───────────────▼─────────────────────────────┐
│ 服务层  services.py                         │
│ 工单下发 / 工序展开 / 报工 / 设备联动 / 汇总   │
└───────────────┬─────────────────────────────┘
                │ ORM
┌───────────────▼─────────────────────────────┐
│ 数据层  SQLite + SQLAlchemy                 │
│ Product / Route / Equipment / WorkOrder     │
│ WorkOrderOperation / ProductionRecord       │
│ EquipmentEvent                              │
└─────────────────────────────────────────────┘
```

设计原则：
- **分层解耦**：路由只做参数校验与响应，业务规则集中在 `services.py`，数据访问在模型层。
- **状态机驱动**：工单 `draft → released → in_progress → completed → closed`；工序 `pending → in_progress → done`。
- **事实不可变**：每次报工写入一条 `ProductionRecord`，工序/工单汇总由事件累加，保留完整追溯。
- **资源联动**：工序开始/结束时自动切换设备状态并写 `EquipmentEvent`，设备监控与生产数据天然一致。
- **零前端构建**：原生 ES Modules + FastAPI StaticFiles，启动后端即可得到完整 UI，降低环境依赖。
- **易扩展**：新增模块只需加一张表 + 一个 router + 一个前端 page 模块；后续可替换为 React/Vue、PostgreSQL、MQTT/OPC UA 采集。

## 业务闭环

1. 主数据：产品 + 工艺路线（工序序列）+ 设备。
2. 创建生产订单 → 按工艺路线展开为工单工序（全部 `pending`）。
3. 下发订单 → 首工序 `in_progress`，关联设备置为 `running`。
4. 工序报工（合格数/不合格数/操作人/设备）→ 写生产记录，累加工序数量。
5. 当前工序数量达标 → 工序 `done`、设备 `idle`；自动进入下一工序或整单 `completed`。
6. 看板实时聚合规订单进度、产量、合格率、设备状态与 OEE 近似指标。
7. 数据采集页可按订单/工序/设备筛选所有报工记录，形成追溯链路。

## 启动

```powershell
cd mes-framework/backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

浏览器打开 http://127.0.0.1:8010/ 。首次启动自动建表并写入演示主数据与一个已下发的演示工单。

API 文档：http://127.0.0.1:8010/docs

## 目录

```
mes-framework/
├─ README.md
├─ requirements.txt
└─ backend/
   ├─ requirements.txt (同根目录)
   └─ app/
      ├─ main.py           # 应用装配 + 静态托管
      ├─ database.py       # 引擎 / Session
      ├─ models.py         # 数据模型
      ├─ schemas.py        # Pydantic 模型
      ├─ services.py       # 业务状态机
      ├─ seed.py           # 演示数据
      └─ routers/          # master / orders / equipment / records / dashboard
   └─ frontend/
      ├─ index.html
      ├─ styles.css
      └─ js/               # api / dashboard / orders / operations / equipment / records / main
```
