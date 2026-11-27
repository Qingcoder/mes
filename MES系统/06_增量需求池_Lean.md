# 戴盟 MES · 增量需求池（Lean / AI 可读）

> 用途：对话沉淀 → 结构化需求。AI 读本文件即可获得 V1 之后的全部增量需求，无需回溯聊天记录。
> 语法：首行 `ID | 模块 | 优先级 | 状态`，下接字段块。
> 状态：`TODO` 待做 / `WIP` 进行 / `DONE` 完成 / `DEFER` 延后 / `ASK` 待确认
> 优先级：`P0` 阻塞 / `P1` 高 / `P2` 中 / `P3` 低
> 来源标记：`D+日期` = 对话日期；无日期者为项目既有约束。

---

## CONST · 硬约束（不可违反）

- C1 数据主权：涉及公司 → 不上云；仅本地 + OneDrive 便携层。
- C2 参照系统 `10.30.120.18:8080` 只读、不动网页、不复用源码。
- C3 改动范围：用户指定改哪就动哪；原件只读，改在副本；其余逐字一致。
- C4 真密码 `admin/123456`；`123456` = 浏览器 autofill 假象，禁止写回代码。
- C5 服务非开机自启；电脑重启后需手动启动（双击 `启动.bat`）。
- C6 工作区代码 = 开发本体 `D:\Program Files\Tencent\2026-11-18-19-16-21\daimon-mes\`；桌面 `daimon-mes\` = 交付副本。二者会漂移，改前确认服务指向谁。

---

## R-01 | UI.LOGIN | P2 | DONE

- 需求：登录页 logo 换官方黑白矢量，加动画可变红；背景改科技感（钢铁侠反应堆）。
- 实现：`src/assets/daimon-logo.svg`（官网 logo.svg，含"戴盟"+DAIMON ROBOTICS，路径未改）；`DaimonLogo.vue` 白→红 8s 呼吸 + hover 定格红；左侧深色 HUD：conic-gradient 同心环 + 刻度 + 红弧 + 暗盘 + 红光呼吸 + 网格 + 准星。
- 验收：截图目视 logo 完整不重叠、hover 变红、环层次清晰。
- 来源：D11-19~20

## R-02 | UI.LOGIN.COPY | P3 | DONE

- 需求：调整登录页文案；删除左侧副文案。
- 实现：标题保留 `MES 生产管理平台`；副文案"记录不再靠纸和群消息…"已整段删除（D11-23）。
- 来源：D11-19 / D11-23

## R-15 | UI.LOGIN.LAYOUT | P2 | DONE

- 需求（两版迭代，最终态）：
  - v1 17:22：logo 横幅（图1）放进登录表单（图2）；深色科技背景（图3）作全局背景。
  - v2 17:32：**logo 移到页面左上角；登录卡居中；右侧白色面板去掉**——整页统一深色科技背景。
- 实现（v2 最终）：`App.vue` 登录页改为单容器全屏——`.login-top-logo`（左上官方 logo）+ `.bg-core`（反应堆 5 环作背景水印，居中）+ `.login-center`（居中表单卡）+ `.foot`；删除旧 `.login-left/.login-right/.hero/.core` 分栏。`Login.vue` 去掉卡内 logo 横幅（logo 已在左上）。`.login-card` 改白底圆角卡 + 红边光晕，浮在深色背景上。
- 验收：无缓存截图（Playwright no-store）DOM 检测通过——标题/左上角 logo/5 环/123456 提示均在；桌面截图目视 logo 左上、卡居中、无右侧白面板。
- 坑：临时静态服务器无 no-cache 时 Playwright 复用旧缓存，截图显示旧文案；加 `Cache-Control: no-store` 头后正常。截图哈希不同证明已更新。
- v3 17:37：补左上角品牌区——logo + "MES 生产管理平台"标题（蓝竖线点缀），首页三要素齐（戴盟/生产管理平台/登录模块）。
- v4 18:13：登录卡只保留用户名/密码/登录（删标题/副标题/底部提示）；卡片改透明毛玻璃（rgba(255,255,255,.82)+backdrop-filter blur(18px)）；加账号/扫码 Tab 切换（见 R-10）。
- 来源：D11-23 17:22 / 17:32 / 17:37 / 18:13

## R-16 | UI.DESIGN-SYSTEM | P1 | DONE

- 需求：所有页面和组件统一四色全局风格——① 红色钢铁侠 ② 黑色 ③ 蓝色科技感 ④ 白色易识别。
- 约束：品牌规范禁蓝作主色 → 红仍是主色，蓝仅点缀（细线/光晕/数据高亮）。
- 实现（`style.css` 设计 token）：
  - ①红：`--red #E61736` / `--red-soft` / `--red-glow`（按钮、激活项、logo呼吸、红弧、卡片红端线）
  - ②黑：`--black #0A0B0D` / `--black-2/3`（侧边栏渐变、深色表头、登录页底）
  - ③蓝：`--tech-blue #3E7BFA` / `--tech-blue-soft/line` / `--tech-cyan`（标题竖线、蓝弧、卡片蓝端线、表头底线、focus光晕、hover左边线）
  - ④白：`--white` + 白底表单/卡片黑字高对比（输入框、数据区、登录卡）
- 落地位置：侧边栏（黑底+蓝线+红激活+白字）、顶栏（蓝底线）、卡片（红蓝渐变顶线）、表头（黑底蓝线白字）、输入焦点（蓝光晕）、登录环（红弧+蓝弧对置）、Vant 变量（主色红，active 蓝）。
- 验收：无缓存截图 + 计算样式确认——侧边栏 linear-gradient(20,21,24→10,11,13)、表头 rgb(31,33,38)；登录页/业务页目视四色协调、可读性无问题。
- **v2 18:08 配色反转**：用户改主次——**蓝白为主调，黑红为装饰**。蓝 `--tech-blue #2E6FE8` 升主色（按钮/导航激活/Vant主变量/卡片线主段/登录按钮）；白为主内容底；黑退为装饰（侧边栏/表头深色底、正文）；红 `#E61736` 仅装饰点（logo方块/头像/卡片线起点/红弧）。登录页背景由黑改深蓝渐变 `#10224A→#040B1C`。注：与旧品牌规范"禁蓝作主色"冲突，以用户最新指令为准。
- 来源：D11-23 17:36 / 18:08

## R-17 | UI.USER-MENU | P2 | DONE

- 需求：顶栏"角色菜单栏要写详细点"——原来只有一个"退出登录"按钮。
- 实现：`api.ts` 加 `setUser/getUser`（localStorage `mes_user` 存 username/name/role）；`Login.vue` 登录成功存用户信息；`App.vue` 顶栏改详细角色菜单——头像(红装饰)+姓名+角色徽标(`admin`→"系统管理员")+下拉箭头；下拉含 4 行详情（账号/角色/身份标识/系统）+ 退出登录按钮。点击外部自动关闭（document click 监听）。手机端隐藏文字只留头像。
- 验收：无缓存截图——触发器 1 个、下拉 4 行、组件库导航 0 个。
- 来源：D11-23 18:07

## R-18 | CLEAN.DEMO | P3 | DONE

- 需求：组件库演示不要给用户看，"你自己维护"。
- 实现：从侧边栏移除"组件库"导航项；删 `/components` 路由、`ComponentsDemo.vue`（工作区+桌面）、titles 映射；Vant 库本身保留（已是全局样式基础）。无残留引用。
- 来源：D11-23 18:07

## R-03 | ACCESS.MOBILE | P1 | DONE

- 需求：手机浏览器可登录、可扫码进入、可当 App 用。
- 实现：后端 `0.0.0.0:8007` 同端口托管 `frontend/dist`（SPA fallback）；PWA manifest + 192/512/180 图标；`手机扫码入口.html` + `手机登录二维码.png`（segno，指向 `http://10.30.121.220:8007/`）。
- 验收：手机同 WLAN 扫码 → 登录页 200。
- 风险：IP 变（换 Wi-Fi / 重启）→ 二维码失效，需重生成。
- 来源：D11-19~20

## R-04 | DOC.KNOWLEDGE | P3 | DONE

- 需求：讲解后端实现（学习用途）。
- 实现：已口头交付——7 表 ORM、登录/工单/SN导入/过站/返修/装箱/三维度查询、状态机服务端校验、幂等、防跳站；`DB_URL` 可切 PostgreSQL。
- 来源：D11-19

## R-05 | SEARCH.GLOBAL | P1 | TODO

- 需求：全局查询框。**自动识别输入类型**——SN、账号名、或数据库里任何存在的字段，均可查到并展示详情页。
- 输入：`string`（不指定类型，系统自动判别）
- 匹配域（建议按此优先级探测）：`unit.sn` / `account.username` / `wo.wo_no` / `box.box_no` / `product.code|name` / `unit.fail_code` / `operator`
- 输出：命中列表 → 类型自适应详情页（SN→过站履历；账号→用户信息；工单→工单进度；箱号→装箱清单）
- 未命中：明确提示"无匹配"，不静默
- 验收：输入 `DAP93226AS00019D` 出 SN 详情；输入 `admin` 出账号详情；输入 `WO-DEMO-001` 出工单详情；输出均含可追溯字段。
- 现状：仅按 SN/工单/箱号三分离查询，**自动识别未实现**。
- 来源：D11-23 10:10

## R-06 | UI.RESPONSIVE | P1 | DONE

- 需求：手机端布局用媒体查询适配 + 兼容性适配。
- 实现（≤768px）：侧边栏→底部 Tab（4 项，当前页红高亮）；表格 `.table-scroll` 横滑（`scrollWidth` 827→390）；按钮/输入放大触屏尺寸；`inputmode=numeric`。
- 兼容：`env(safe-area-inset-bottom)` 刘海屏、`100dvh` 动态视口、`16px` 输入防 iOS 缩放、`-webkit-tap-highlight-color` 去高亮。
- 验收：5 页（登录+4业务）手机视口无横向溢出；截图目视通过。
- 来源：D11-20

## R-07 | UI.COMPONENT | P1 | WIP

- 需求：权限清单那种"分组 + 勾选卡片"做成通用组件；用户改口 → **直接引入成熟 Vue3 移动端组件库**。
- 决策：选 **Vant 4**（Vue3+TS 原生、移动端专门设计、npm 可达）；弃 Element Plus（PC 起家）。
- 实现：`npm i vant@4.10.2` + `qrcode@1.5.4`；`main.ts` 全量 `.use(Vant)` + `import 'vant/lib/index.css'`；`style.css` 覆盖 `--van-primary-color: #E61736` 等变量。
- 演示页：`views/ComponentsDemo.vue`，同份数据两种形态（卡片网格 `auto-fill minmax(200px,1fr)` / `van-collapse`+`van-cell`+`van-checkbox` 折叠多选），修复截图里文字竖排缺陷。
- 路由 `/components`，导航项"组件库"。
- 待办：全量引入使 CSS 11KB→214KB、JS 131KB→366KB，如在意体积改按需引入（unplugin-vue-components + @vant/auto-import-resolver）。
- 状态核实：D11-23 的服务曾指向桌面副本导致本改动未生效，已切回工作区；需目视确认演示页。
- 来源：D11-23 13:57

## R-08 | ui.permission | P3 | DEFER

- 需求来源：用户截图（权限清单）——工单/生产/查询/系统四组，含 `wo:view`、`wo:create`、`sn:import`、`station:op`、`rework:op`、`pack:op`、`query:view`、`user:manage`、`role:manage`。
- 现状：该界面不在当前工程（来自参照系统）；仅作为 R-07 组件演示的样例数据。
- 若后续要真做：需后端补权限表 + 角色绑定，前端补角色管理页。
- 来源：D11-23 13:57

## R-09 | OPS.SERVICE | P1 | DONE(部分)

- 需求：后台服务帮我维持着。
- 现状：可后台启动，会话内存活；会话结束/电脑重启即停。
- 用户偏好：曾问"要不要开机自启"，未明确答复 → `ASK`。
- 陷阱：D11-23 发现 8007 曾被**桌面副本** `Desktop\daimon-mes\backend` 占用，导致工作区改动不可见。排查命令：`Get-NetTCPConnection -LocalPort 8007` → 取 PID → `Get-CimInstance Win32_Process` 看 CommandLine。
- 来源：D11-23 13:53 / 16:54

## R-10 | AUTH.SCAN | P1 | DONE

- 需求：登录框里加**可切换扫码登录**。
- 硬要求：必须真实可用，禁止"假扫码 / 表面渲染"（用户明确点名过此坑）。
- 实现（设备授权模式，已落地）：
  - 后端 `main.py` 加内存状态机：`POST /api/qr/create`（发 sid，TTL 300s）、`GET /api/qr/status?sid=`、`POST /api/qr/confirm?sid=`（需 Bearer demo-token，绑定 admin 身份）。过期自动清理，一次性消费。
  - 前端 `Login.vue` 加账号/扫码 Tab；扫码用 `qrcode@1.5.4` 生成二维码，内容 = `location.origin/scan-approve?sid=`；1.5s 轮询 status，confirmed 则 setToken/setUser 跳 `/wo`，expired 提示刷新。
  - 手机确认页 `views/ScanApprove.vue`：显示会话/确认身份/有效期，点"确认登录"调 confirm；带安全提示。
  - 路由：`/scan-approve` 加入 publicPages 免登录；App.vue 三分支（登录页/确认页裸渲染/主应用）。
- 验收：curl 端到端——pending→确认→confirmed(带user admin/系统管理员)→重复确认被拒；浏览器——Tab 切换、二维码 img、确认页 3 行详情、无 JS 错误。
- 来源：D11-23 16:54 / 18:13

## R-11 | MEMORY | P1 | DONE

- 需求：把整个项目记忆沉淀进本地；大型项目记忆要多层结构。
- 结论：必须多层，三个硬约束——上下文窗口有限 / 读取频率差两个数量级 / 变更速率不同。
- 五层：`L0` 身份与偏好（SOUL/IDENTITY/USER）→ `L1` 项目索引（工作区 `MEMORY.md`，每次注入，只放固定事实+指针）→ `L2` 主题域（按需读）→ `L3` 流水日志（只追加，30 天蒸馏进 L1/L2 再删）→ `L4` 便携交接（OneDrive 项目包，纯 Markdown）。
- 三条纪律：索引与正文分离；写入分流（踩坑→lessons，进度→日志，决策→主题）；蒸馏闭环。
- 已落地：工作区 `MEMORY.md`（2090 字符）、`OneDrive\MemoryKit\projects\戴盟MES\项目记忆.md`（8.3KB）、`START-HERE.md` 加索引。
- 来源：D11-23 08:43

## R-12 | BUG.CACHE | P1 | DONE

- 需求：截图 `Failed to fetch` + 底部仍显示 `admin/123456`。
- 根因：浏览器缓存旧 `index.html`，其引用旧 hash JS（已被新构建删除）→ 404 → 脚本失效。服务端本身正常。
- 修复：`backend/app/main.py` SPA 兜底 `FileResponse` 加 `no-store/no-cache/Pragma/Expires`；Vite assets 文件名带 hash 本身防缓存，未动。
- 验收：`GET /login` 返回 `cache-control: no-store`；全新浏览器登录成功跳转 `/wo`。
- 来源：D11-23 10:10

## R-13 | OPS.CODE-SYNC | P0 | DONE

- 需求：多处代码副本一致性。
- 现象：8007 返回 `index-EGUXqMdp.js` + 导航"首页/用户/角色权限"，与工作区工程（"工单/过站/装箱/数据"）不符。
- 根因：服务从**桌面副本**启动（PID 命令行证实 `Desktop\daimon-mes\backend\.venv\python.exe`）。
- 处置：停桌面副本进程 → 工作区重新构建 → 从工作区 `backend` 启动。
- 规则：改代码前先确认服务指向的工作目录；两处副本需显式同步（改动后 `cp` 到桌面 + 重打 tar.gz）。
- 来源：D11-23 16:54

## R-14 | DOC.LEAN | P2 | DONE

- 需求：把对话里发的需求收集进架构需求；转成 AI 可阅读的高效 lean 语言。
- 实现：本文件 `06_增量需求池_Lean.md`；首行元数据 + 字段块，无叙述性废话。
- 来源：D11-23 17:00

---

## R-19 | WO.FLOW-COMBO | P1 | DONE

- 需求：工单支持**组合多条产品流程**（原为单选一条流程）。
- 语义：勾选 N 条流程 → 按右侧顺序合并站点序列（顺序拼接，重复站点保留首次出现）→ 作为该工单的过站序列；工单同时记录组合明细（各流程的 key/名称/站点）。
- 实现：
  - 后端 `models.WorkOrder` 新增 `flows` JSON 列；`main.py` 加 `_migrate_wo_flows_column`（幂等 ALTER TABLE + 旧行补 '[]'，因 create_all 不给旧表加列）、`merge_flow_stations`、`normalize_flows`；`POST /api/wos` 传 `flows` 时由后端派生 `stations`，不传则保持老单流程行为；空流程直接 400。
  - 前端新增 `components/WoFlowCombo.vue`（勾选 + 上移/下移 + 合并预览 + 重复站点提示）、`types/flow.ts`；`views/WO.vue` 改为组合选择器，工单列表显示"组合 N 条流程"。
- 兼容：老工单 `flows` 为空数组，站点序列仍是过站校验唯一依据，过站/装箱/查询逻辑零改动；前端同时提交 `stations` 与 `flows`，旧后端也能正常建单。
- 验收：隔离环境（8017 + 复制库）HTTP 自测 18/18 PASS —— 旧库自动补列、旧工单 flows 为空、单流程建单、组合建单合并序列正确、组合明细回显、空流程 400、详情回显、人员 scope、设备筛选、环境域 stations 键。
- 边界：目前是"一单一套站点序列"。若要"一单多产品各自走不同流程"（SN 按产品分轨），需另设计 SN 的产品归属与分轨过站，尚未实现。
- 来源：D11-27

---

## R-20 | ENV.READONLY | P1 | DONE

- 需求：共享资料库**先只做查看和查询，不能改**；写入/编辑功能用户会在别处实现。
- 实现（前后端双层拦截）：
  - 后端 `routers/environment.py`：新增 `_readonly_mode()`（读环境变量 `MES_ENVIRONMENT_READONLY`，默认 "1" 即只读）与 `_readonly_guard()`；上传 `POST /resources`、编辑 `PUT /resources/{id}`、删除 `DELETE /resources/{id}` 三个写接口挂 `dependencies=[Depends(_readonly_guard)]`，只读时返回 403「共享资料库当前为只读模式，写入入口迁移中」。
  - **闸门必须挂路由依赖、不能写函数体**：FastAPI 先做请求体校验再进函数体，写函数体等于先把整个上传文件收完才拒绝。
  - 前端 `components/EnvironmentResourcePanel.vue`：移除上传区（拖拽/选择/表单/关联对象）、行内「编辑」「删除」按钮与编辑弹窗，并清掉相应死代码（upload/openEdit/saveEdit/remove/options/form 等）；保留查看、下载、历史、模块/类别/关键词检索、刷新、模块总览；页面加只读提示条。
- 放开方式：把环境变量 `MES_ENVIRONMENT_READONLY` 设为 0（false/off 亦可）即恢复写入，无需改代码；用户后续在别处实现写入功能时可直接复用这套接口。
- 验收：隔离环境（8017 只读 + 8018 可写）HTTP 自测 9/9 PASS —— 列表/总览/选项可查；上传/编辑/删除均 403 且提示只读；未登录 401；开关置 0 后写入口放行。vite build 通过。
- 遗留：`StationMasterPanel`（自定义站点/站点分组）仍挂在同一页面且可写，与「自定义站点」页功能重复，待用户确认收敛到哪一处。
- 来源：D11-27

---

## R-21 | CHAIN.FLOW-STATION-PRODUCT | P1 | DONE

- 需求：先把「流程 → 站点 → 产品」这条主路跑通（端到端实证，不是接口存在即算通）。
- 做法：隔离环境（8017 + 复制库）写端到端脚本，按真实数据走 工艺管理 → 建单 → 导入SN → 逐站过站 → 装箱 → 三维度查询 → 不良 → 返修，共 26 项断言。
- 实证结果：**26/26 PASS**。链路：主线流程 → OP10/OP20/OP30 → 产品档案 → 工单（站点序列派生 + 流程明细 + 跨域关联）→ 产品档案自动带上站点 → SN 导入 → 过站三校验（跳站被拦）→ 装箱（未过完被拦）→ SN/工单/箱号查询 → 不良转维修站 → 返修回原站重测。
- 途中修掉 3 个真断点：
  1. **产品关联错位**：`resolve_relation_code` 名称与编码混着比，命中第一个同名项（库里有两个产品都叫"V2.9 无本体数采背包"）→ 改为**先精确比 code、再比 name**；`WOIn` 增 `productCode`，建单按编码关联。
  2. **无档案产品建单后关联无处落地**：产品↔站点的关联写在产品档案里，无档案产品（models.Product 老表独有条目）选了就挂不上 → 建单下拉只列 `hasProfile` 的产品（5/8），后端加防错：产品无档案直接 400「请先在产品资料创建档案」。
  3. **返修后当前站停在维修站**：fail 时当前站被改写成维修站，rework 只改 state 不还原站点 → rework 现在从过站记录取回**失败站**并回写 current_station，返回「已回到 XX 站重测」。
- 前端：建单页产品下拉改用编码选中（`name（code）`），过滤无档案产品，无档案时提示去「产品资料」建档案。
- 遗留噪音：产品档案的 relatedStations 里会出现「维修站（R100）」——维修站经维修处理流程分组连到工单，属传递闭包结果，不影响主链路，是否过滤待定；产品档案里仍有 code 为中文名的历史脏数据，建议在产品资料页合并。
- 来源：D11-27

---

## R-22 | NAV.TREE | P1 | DONE

- 需求：侧边栏路由改成「不相关的平铺 + 有上下级的树结构」。
- 实现：
  - `routeConfig.ts` 新增 `parent` 字段声明父子关系（唯一数据源，不另建一份菜单树）；`group` 字段保留但不再渲染标题。
  - 父子关系：物料管理 → 产品资料、SN 库；工艺管理 → 自定义站点、站点流程权限。其余菜单项无真实从属关系，一律平铺。
  - `validateRouteConfig` 新增校验：parent 必须指向存在的菜单项、不能自指；菜单项不再强制 group。
  - `App.vue`：`menuGroups` 改为 `menuTree`（顶层平铺 + 子项挂树），父项右侧 `›` 箭头展开/收起，展开态存 localStorage（`mes_nav_expanded`），进入子页自动展开其父级；顶部新增「同族子页快捷条」，手机端底部 Tab 放不下树时靠它进子页。
  - `style.css`：新增树形样式（子项缩进 + 引导线 + 箭头旋转），移动端隐藏树只留顶层项。
  - 菜单顺序：权限管理 order 22→40（从站点作业之前移到最末）。
- 实证：真实浏览器登录后读取 DOM —— 分组标题 0 个（平铺生效）、物料管理带箭头且当前页祖先自动展开、点箭头收起/展开生效且展开态持久化（localStorage ["/material"]）、子页顶部快捷条显示 [产品资料, SN 库]。截图 docs/nav_tree_expanded.png / nav_tree_collapsed.png / nav_tree_child.png。
- 来源：D11-27

---

## R-23 | NAV.GROUPS | P1 | DONE

- 需求：把原 5 组导航精简合并为 3 组，明确各组排序、默认展开状态与权限要求；功能项一个不少，只调整归属与顺序。
- 分组定义（`routeConfig.ts` 新增 `NAV_GROUPS`，唯一数据源）：
  | 组 | 顺序 | 默认 | 可见性 | 成员 |
  |---|---|---|---|---|
  | 现场作业 | 1 | 展开 | 无额外要求 | 站点作业、包装管理、数据追溯 |
  | 生产主管 | 2 | 展开 | 无额外要求 | 看板、工单管理 |
  | 配置中心 | 3 | **折叠** | 需至少一个 `system:*` 权限 | 人员/设备/物料/工艺/共享资料库（人机料法环五项）+ 产品资料 + SN 库 + 自定义站点 + 站点流程权限 + 权限管理 |
- 实现：
  - 路由项新增 `group`（分组 key），`validateRouteConfig` 校验「菜单项必须归属已定义分组」——分组写错会静默丢菜单，必须启动即报错。
  - `App.vue`：`menuTree` 改为 `navGroups`（分组 → 条目 → 条目子项）；组标题可点击展开/收起，状态存 localStorage（`mes_nav_groups`），用户切换后覆盖默认值。
  - 组可见性由 `requirePermPrefix` 决定（配置中心 = `system:`）；组内条目仍按各自权限过滤；**父项无权限但子项有权限时子项提升为组内顶层**，功能不丢。
  - 进入某组页面的页面时自动展开该组（否则刷新后看不到自己在哪组）；手机端底部 Tab 放不下分组与树：隐藏组标题、组内平铺，子项靠页面顶部快捷条进入。
- 实证（真实浏览器）：三组顺序 现场作业→生产主管→配置中心；全新状态展开态 = 现场作业=true / 生产主管=true / **配置中心=false**（默认折叠）；配置中心展开后组内 6 个父项 + 产品资料/SN库/自定义站点/站点流程权限 齐全；角色预览切到 role_002（system:* 0 项）后**配置中心整体不出现**。截图 docs/nav_groups_default.png / nav_groups_admin.png / nav_groups_expanded.png / nav_groups_preview.png。
- 来源：D11-27

---

## 待确认（ASK）

- A1 服务是否配开机自启？用户曾问未答。（R-09）
- A2 全局查询框匹配域与详情页字段，按 R-05 建议还是另有指定？（R-05）
- A3 扫码登录用"设备授权"模式是否接受？还是简化为扫码直接带入 SN？（R-10）
- A4 Vant 全量引入体积翻倍，是否转按需引入？（R-07）
