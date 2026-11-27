# KTG-MES 架构参考（苦糖果 MES）

> 文档编号：03
> 调研日期：2026-11-19
> 用途：架构源文件，供 AI 转化为设计 / 代码
> 定位：**设计参考，不是改造底稿**——本项目已定绿场自研

---

## 1. 它是什么

| 项 | 内容 |
|---|---|
| 名称 | 苦糖果 MES（KTG-MES） |
| 定位 | 国内基于 RuoYi 前后端分离版开发的通用开源 MES，面向中小离散制造 |
| 后端仓库 | https://gitee.com/kutangguo/ktg-mes |
| 前端仓库 | https://gitee.com/kutangguo/ktg-mes-ui |
| 许可 | MIT（仓库 LICENSE） |
| 活跃度 | Gitee 5k+ star，镜像仓库最近提交约 11 个月前 |
| 在线体验 | http://www.029tec.com |

## 2. 技术栈与规模

| 层 | 选型 |
|---|---|
| 后端 | Spring Boot 2.5.0 + Spring Security + MyBatis-Plus 3.4 + Druid |
| 前端 | Vue 2.6 + Element UI 2.15 + ECharts 5 + Axios |
| 中间件 | MySQL 5.7 + Redis 6.2 + RabbitMQ + MinIO |
| 部署 | Docker Compose（前端 8000 / 后端 8007 / MySQL 8001） |

**规模：176 张表**。分布：仓储 64、系统 23、生产 20、质量 16、主数据 14、设备 13、Quartz 11、日历 7、其他 8。

这是一个重要信号：它已经不是"轻量 MES"，而是一套完整 ERP-MOM 体系。对我们 V1 的 4 模块而言，176 张表是**反面参照**，不是起点。

## 3. 功能范围

- **PC 端**：系统管理、主数据（物料产品/工作站）、生产管理（排产/工单）、质量管理、生产排班、仓储管理、设备管理、统计报表、大屏展示
- **触屏端**：生产、质量、工序、设备
- **PDA**：仓储、生产
- **Android**：生产、质量、仓储、设备

## 4. 值得借鉴的三处设计

### 4.1 工单 → 任务 → 报工 → 质检 → 入库 的链路

核心表与关系：

| 表 | 职责 |
|---|---|
| `pro_workorder` | 工单主表 |
| `pro_workorder_bom` | 工单用料 |
| `pro_route_process` | 工艺路线工序定义 |
| `pro_task` | 工单拆分出的生产任务 |
| `pro_feedback` | 工序报工记录 |
| `qc_ipqc` | 制程检验，通过 `source_doc_id` 关联 `pro_feedback` |

**可借鉴点**：报工和质检用 `source_doc_id` 做引用式关联，而不是把检验字段塞进报工表。这让一条报工可以挂多条检验，且质检模块能独立演进。

### 4.2 报工的"数量四分法"

`pro_feedback` 把报工数量拆成四个字段：

- `quantity_feedback`（报工数）
- `quantity_qualified`（合格数）
- `quantity_unquanlified`（不合格数）
- `quantity_uncheck`（待检数）

配合 `is_check` 标志位，形成：**报工 → 待检 → 判定合格/不合格** 的清晰状态。

**可借鉴点**：我们的过站作业可以直接用这个模型，站在 SN 级别记录"通过/待检/不合格"，不用引入复杂质检模块。

### 4.3 统一待检队列

RuoYi MES 的 `PendingInspect` 用一条 `UNION ALL` 把 6 个不同业务来源的待检任务聚合成一个队列，质检员只看一个页面。

**可借鉴点**："统一入口 + 分类处理"——我们 V1 虽只有过站一个来源，但数据模型要预留 `source_type` 字段，避免以后加来源时重构。

## 5. 不能照搬的四处

| 项 | 原因 |
|---|---|
| 176 张表 | 远超 V1 的 4 模块需要，照搬即范围失控 |
| Java + Redis + RabbitMQ + MinIO | 与立项单的 Python FastAPI + SQLite 选型冲突，运维成本翻倍 |
| RuoYi 权限体系 | 我们 V1 延后账户权限模块，不需要 23 张系统表 |
| 触屏端 / PDA / Android | 已写进排除清单（不做移动端） |

## 6. 与我们 V1 的映射

| 我们的模块 | 对应借鉴 | 简化做法 |
|---|---|---|
| 工单维护 wo | `pro_workorder` + `pro_workorder_bom` | 只保留工单 + 产品 + 计划数 + SN 清单，不做排产 |
| 过站作业 op | `pro_feedback` 四分法 + `is_check` | SN 级记录，站点顺序校验，不做工序任务拆分 |
| 包装出库 pack | WM 出入库链路 | 按配比装箱，不引入 64 张仓储表 |
| 数据查询 query | `source_doc_id` 引用式关联 | 按 SN 正反向追溯，不做全批次谱系 |

## 7. 状态机设计要点（通用实践，非 KTG 专有）

成熟 MES 的工单状态机：

`待排产 → 已排产 → 已下发 → 生产中 → 已完工 → 已入库`

**关键纪律**：状态流转收敛在服务层统一方法里，页面只调方法、不直接改状态。校验规则（如"未下发不能报工"）写在一处，不散落在各页面。

这条对我们尤其重要——我们 V1 的 SN 状态流转（`pending → passed → failed → packed`）也应按此设计。

---

## 8. 结论

**KTG-MES 的正确用法是"读设计，不搬代码"**：

1. 读它的 `pro_feedback` 数量四分法和 `source_doc_id` 关联方式
2. 读它的工单状态机收敛原则
3. 不部署、不改造、不引用它的 176 张表

调研结论支持立项单现有决策：绿场自研，V1 四模块，借鉴设计而非复用实现。

---

**资料来源**：Gitee ktg-mes / ktg-mes-ui 仓库、DeepWiki KTG-MES 源码解析、云表《10 款免费 MES》、CSDN MES 车间管理源码解析、腾讯云《MES 开发：从工单闭环到数据追溯》
