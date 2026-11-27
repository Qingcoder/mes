---
name: restore-login-page
overview: 优先确认登录页是否因前端构建产物过期导致旧页面/旧登录逻辑仍在运行；在保持现有登录页结构与组件拆分的前提下，同步构建、重启后端并完成真实登录回归验证。
todos:
  - id: verify-login-source
    content: 核对 `/login` 路由、登录页组件和真实令牌链路，确认是否仅需重建产物
    status: completed
  - id: restore-login-minimal
    content: 仅做必要局部修复，恢复登录页展示与真实令牌保存，不重写页面
    status: completed
    dependencies:
      - verify-login-source
  - id: rebuild-login
    content: 执行类型检查与 Vite 构建，确认新产物包含登录组件且无旧 demo-token
    status: completed
    dependencies:
      - restore-login-minimal
  - id: restart-and-verify-api
    content: 重启后端并验证登录接口、权限接口和二维码状态接口
    status: completed
    dependencies:
      - rebuild-login
  - id: browser-login-regression
    content: Use [skill:playwright-cli] 验证 `/login` 展示、错误登录、真实登录、刷新与页面跳转
    status: completed
    dependencies:
      - restart-and-verify-api
  - id: login-regression-pages
    content: 回归 `/station`、`/roles` 等页面，确认登录恢复未影响其他功能
    status: completed
    dependencies:
      - browser-login-regression
---

## 需求概述

用户要求“把登录页面弄回来”。结合现有上下文，目标是恢复 `/login` 的正常展示与登录能力，同时继续使用真实账号、真实令牌和现有登录页结构，不引入演示模式、固定令牌或假数据。

## 核心目标

- 恢复登录页在 `/login` 的完整展示：品牌背景、登录卡片、账号登录、扫码登录。
- 保持现有页面结构，不整页删除或重写 `Login.vue`。
- 保留已拆分的 `AuthTabs.vue`、`PasswordLoginForm.vue`、`QrLoginPanel.vue` 组件。
- 密码登录成功后保存服务端返回的真实令牌，并进入真实权限对应首页。
- 扫码登录确认后使用服务端返回的真实令牌完成登录。
- 修复登录页不可见、旧构建残留或旧登录逻辑仍被加载的问题。
- 不新增演示模式、静态假数据或占位登录逻辑。

## 技术判断

当前登录页源码仍存在，`/login` 路由仍注册为 public，登录组件也完整。主要风险点是前端构建产物落后于源码：

- `frontend/src/views/Login.vue` 修改时间晚于 `frontend/dist/index.html`
- 当前 dist 产物仍包含旧 `demo-token` 登录逻辑
- dist 产物不包含最新的 `AuthTabs`、`QrLoginPanel` 组件特征

因此本任务按“先确认源码、再重建产物、最后做真实登录回归”的顺序处理。

## 涉及模块

1. `frontend/src/router/routeConfig.ts`

- 确认 `/login` 仍为 public 路由。

2. `frontend/src/App.vue`

- 确认 `isLogin` 分支仍渲染登录页外壳和背景。

3. `frontend/src/views/Login.vue`

- 保留现有组件组合，仅在必要时做小范围修复。

4. `frontend/src/components/AuthTabs.vue`

- 登录方式切换展示。

5. `frontend/src/components/PasswordLoginForm.vue`

- 账号密码表单与提交事件。

6. `frontend/src/components/QrLoginPanel.vue`

- 二维码展示与刷新入口。

7. `frontend/src/api.ts`

- 确认登录请求、令牌保存、`myPermissions` 调用链路一致。

8. `backend/app/main.py`、`backend/app/auth.py`、`backend/app/routers/roles.py`

- 确认登录签发真实令牌，权限接口从令牌解析账号。

9. `frontend/dist`

- 通过重新构建更新，不手工修改构建产物。

## 实现策略

- 优先确认源码是否已经完整；若完整，不做重复改造，只执行构建与运行验证。
- 若发现登录页结构缺失，仅做局部补丁，不重写页面。
- 若发现仍使用 `demo-token`，只修复登录和令牌相关链路。
- 不在本次任务中扩展其他业务页面。
- 不新增数据库结构，不修改业务数据。
- 不引入新前端框架或扫码库，复用现有 Vue 3、Vant、ZXing 和现有组件。

## 执行注意

- 重建前先执行 TypeScript 类型检查。
- 构建后确认新产物包含登录组件特征，不再包含旧 `demo-token`。
- 后端如加载了新的真实认证逻辑，需要重启后再验证登录。
- 验证时清理浏览器旧 token 和缓存，避免旧 localStorage 掩盖问题。
- 若登录成功但页面不跳转，重点检查 `/api/me/permissions` 的令牌认证和前端 `finishLogin` 流程。
- 若 `/login` 能打开但空白，重点检查 `App.vue` 的 `isLogin` 分支和登录组件渲染错误。
- 若登录接口返回 401 或 422，检查请求体、令牌保存和认证依赖。

## 前端结构

```text
frontend/src/
├── views/
│   └── Login.vue                 # [MODIFY] 仅做必要的局部修复，保持页面结构
├── components/
│   ├── AuthTabs.vue              # [KEEP] 登录方式切换
│   ├── PasswordLoginForm.vue     # [KEEP] 账号密码表单
│   └── QrLoginPanel.vue          # [KEEP] 扫码登录面板
├── types/
│   └── auth.ts                   # [KEEP] 登录模式共享类型
├── router/
│   └── routeConfig.ts            # [VERIFY] /login public 路由
├── App.vue                       # [VERIFY] 登录页外壳与背景
└── api.ts                        # [VERIFY/MODIFY] 真实令牌保存与登录请求
```

## 后端结构

```text
backend/app/
├── main.py                       # [VERIFY] /api/login、二维码状态与令牌返回
├── auth.py                       # [VERIFY] 令牌签发、密码校验
├── schemas.py                    # [VERIFY] LoginOut 字段
└── routers/
    └── roles.py                  # [VERIFY] 令牌身份读取权限
```

## 验收标准

- 访问 `/login` 能看到完整登录页面。
- 错误账号密码显示明确错误。
- 正确账号密码登录成功并保存真实令牌。
- 登录后按真实权限跳转，不进入演示页。
- 刷新登录页仍能正常展示。
- 扫码登录确认后能拿到真实令牌。
- 登录页构建产物不再包含旧 `demo-token` 登录逻辑。
- `/station`、`/roles` 等页面仍可正常访问。

## Agent Extensions

### Skill

- **playwright-cli**
- Purpose: 在恢复登录页后执行真实浏览器验证
- Expected outcome: 打开 `/login`、检查登录表单可见性、验证错误登录提示、完成真实账号登录、确认跳转和刷新后的状态

### SubAgent

- **code-explorer**
- Purpose: 若登录页仍异常，快速定位路由、组件引用、构建产物和认证链路之间的遗漏
- Expected outcome: 给出明确的异常文件与修复点，避免大范围改动