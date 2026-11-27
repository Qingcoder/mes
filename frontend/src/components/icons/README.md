# 图标库模块

统一管理系统图标资源，供导航、模块入口、搜索、扫码和站点卡片复用。

## 目录结构

```text
src/components/icons/
├── AppIcon.vue       # 图标渲染组件
├── index.ts          # 统一导出入口
├── registry.ts       # 元信息、按需加载器、兼容方法
├── types.ts          # 类型定义
├── version.ts        # 图标库版本
├── README.md         # 使用文档
└── sets/             # 按业务域拆分的 SVG path 数据
    ├── common.ts
    ├── domain.ts
    ├── production.ts
    └── system.ts
```

## 命名规则

- 图标 key 使用小写英文，语义优先：`person`、`machine`、`material`、`method`、`environment`。
- 多单词使用小驼峰：`accessControl`。
- 图标含义统一在 `registry.ts` 的 `META` 中维护，不要在页面中写死。
- SVG 路径按业务域放入 `sets/`，一个域一个文件。

## 引入与调用

```vue
<script setup lang="ts">
import { AppIcon } from '@/components/icons'
</script>

<template>
  <AppIcon name="person" :size="18" label="人员管理" />
</template>
```

兼容旧 API：

```ts
import { appIcon, hasIcon } from '@/components/icons'

appIcon('person') // { glyph: '◉', label: '人员管理' }
hasIcon('person') // true
```

## 可配置属性

| 属性 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `name` | `string` | 必填 | 图标 key |
| `size` | `number \| string` | `18` | 数字按 px，字符串可为 `1em`、`20px` |
| `color` | `string` | `''` | 不传时继承当前文字色 |
| `strokeWidth` | `number` | `1.8` | SVG 线宽 |
| `label` | `string` | `''` | 覆盖默认含义，用于 `title` 与无障碍标签 |
| `decorative` | `boolean` | `false` | 纯装饰图标时设为 `true` |

## 默认样式与主题

- 默认 `currentColor`，随菜单、按钮、卡片文字色变化。
- 可通过 CSS 变量 `--icon-color` 统一改色。
- 桌面端与移动端通过 `size` 控制尺寸，不在组件内写死业务尺寸。
- 图标加载前显示字符兜底，加载后替换为 SVG。

## 按需加载与打包

- `registry.ts` 仅保留元信息与加载器。
- SVG 路径按 `sets/` 分组，通过动态 `import()` 加载。
- 同一业务域只加载一次并缓存，避免重复请求。
- 不引入第三方图标库，不生成额外网络字体请求。

## 新增图标流程

1. 在对应 `sets/*.ts` 增加 `key: string[]`，值为 24×24 viewBox 下的 SVG path。
2. 在 `registry.ts` 的 `META` 增加 key、含义、兜底字符和业务域。
3. 如是新业务域，新增 `sets/xxx.ts` 并在 `LOADERS` 注册。
4. 如是破坏性变更，更新 `version.ts` 版本号。
5. 使用 `AppIcon name="新key"` 调用。

## 与现有组件库集成

- 放在 `src/components/icons/`，与现有 `src/components/*.vue` 组织方式一致。
- 通过 `index.ts` 统一导出，页面无需关心内部目录。
- 不包装 Vant 组件，不覆盖 Vant 样式。
- 旧 `src/config/iconRegistry.ts` 保留为兼容层，逐步迁移到新入口。

## 版本管理

版本号位于 `version.ts`，采用语义化版本：

- `patch`：新增图标、修正路径。
- `minor`：新增业务域、新增可配置属性。
- `major`：重命名 key、移除图标、改变 props 语义。
