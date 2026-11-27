# 戴盟 MES 生产管理平台 · 初版

> 对应架构文档：`桌面\MES系统\00_MES自研总纲.md`
> 技术选型：Vue 3 + TypeScript（前端）/ Python FastAPI（后端）/ SQLite（数据库）
> 状态：可运行初版，主链路已验证

## 启动

**一键启动**：双击 `启动.bat`（首次会自动建 `.venv`、装依赖，然后同时拉起前后端）

**或手动**：
```bash
# 后端（监听 0.0.0.0，手机可访问）
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8007

# 前端（开发模式，热更新）
cd frontend
npm run dev
```

**访问**：
- 开发界面 http://127.0.0.1:5173/ （账号 admin / 123456）
- 生产界面（构建产物由后端托管）http://127.0.0.1:8007/login
- API 文档 http://127.0.0.1:8007/docs
- 手机同局域网：`http://<本机IP>:8007/login`，扫码用 `手机扫码入口.html`
- 换电脑见 `换机开发说明.md`

## 目录结构

```
daimon-mes/
├─ backend/
│  ├─ .venv/               # Python 虚拟环境（已装 FastAPI/SQLAlchemy）
│  ├─ app/
│  │  ├─ models.py         # 数据模型：7 张表，ORM 定义
│  │  ├─ schemas.py        # Pydantic 请求/响应模型
│  │  └─ main.py           # API 路由 + 状态机校验 + 登录
│  ├─ mes.db               # SQLite 数据库（含演示数据）
│  └─ requirements.txt     # 依赖清单
├─ frontend/
│  ├─ src/
│  │  ├─ api.ts            # API 客户端封装
│  │  ├─ main.ts           # 入口 + 路由
│  │  ├─ App.vue           # 布局 + 品牌标识
│  │  ├─ style.css         # 全局样式（中国红品牌色）
│  │  └─ views/            # 5 个页面
│  │     ├─ Login.vue      # 登录
│  │     ├─ WO.vue         # 工单 + SN 导入
│  │     ├─ Station.vue    # 过站
│  │     ├─ Pack.vue       # 装箱
│  │     └─ Query.vue      # 查询
│  ├─ dist/                # 生产构建产物
│  └─ vite.config.ts       # 含 /api 代理配置
└─ start-backend.bat       # 后端一键启动
```

## 已实现的主链路

登录 → 建工单（每单配站点序列与装箱配比）→ 导入 SN 清单 → 手机输入 SN 过站 → 装箱封箱 → 按 SN/工单/箱号查询。

**防错逻辑已落地**：
- 不能跳站（服务端按工单站点序列校验）
- 重复过站幂等跳过
- 重复 SN 导入自动跳过
- 未过完站的 SN 不能装箱
- 一箱只能装同一工单的 SN

## 技术说明

### 数据库迁移路径
连接串集中在 `app/main.py` 的 `DB_URL`。SQLite 起步，将来迁 PostgreSQL：
1. `pip install psycopg2-binary`
2. 设环境变量 `MES_DB_URL=postgresql://user:pass@host/db`
3. 无需改业务代码（ORM 已屏蔽方言差异）

### 品牌规范
主色中国红 `#E61736`，详见 `桌面\MES系统\05_品牌与视觉规范.md`。全局集中在 `src/style.css` 的 CSS 变量。

### 安全提醒
V1 单账号密码为演示用明文（admin/123456），正式使用前需改为哈希存储并修改初始密码。

## 学习资料

`桌面\MES系统\技术资料\00_技术学习地图.md` —— 每项技术都带官方文档链接和本项目对应代码位置。

## 验证记录（2026-11-19）

- 后端 13 项接口自测全过（登录/建单/SN导入/过站/跳站拦截/幂等/装箱/三维度查询）
- 前端 TypeScript 类型检查零错误，Vite 构建成功（116KB JS）
- 浏览器实测：登录页渲染正确、登录成功跳转、主界面红色品牌导航正常
- 前后端代理连通，`/api` 请求正常转发
