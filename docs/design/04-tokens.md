# 04 — 视觉令牌（Tokens）

> 状态：首版定稿 · 2026-11-16
> 源文件：Penpot「新建文件 1」→ 页面「主页面」→ 画板「工作台 · 1440」/「工作台 · 侧边收起」
> 令牌集：Penpot 本地库令牌集「基础」（26 个令牌），库颜色 11 个，文字样式 5 个
> 用途：前端实现时**只允许**使用本节列出的值，禁止在组件里写新的十六进制颜色

## 1. 颜色

### 1.1 语义色（已登记为 Penpot 令牌 + 库颜色）

| 令牌 | 值 | CSS 变量 | 用途 |
|---|---|---|---|
| `color.primary` | `#2563EB` | `--color-primary` | 主按钮、选中态、品牌块、链接 |
| `color.primary-hover` | `#1D4ED8` | `--color-primary-hover` | 主按钮 hover、选中文案 |
| `color.accent` | `#06B6D4` | `--color-accent` | 次级强调、徽章前景 |
| `color.warning` | `#F59E0B` | `--color-warning` | 异常提示条、未配置状态点 |
| `color.danger` | `#DC2626` | `--color-danger` | 失败、删除等破坏性动作 |
| `color.success` | `#16A34A` | `--color-success` | 正常状态点、扫描完成 |
| `color.text-primary` | `#0F172A` | `--color-text` | 正文与标题主色 |
| `color.text-secondary` | `#64748B` | `--color-text-secondary` | 次级说明文字 |
| `color.border` | `#E2E8F0` | `--color-border` | 面板分隔、卡片描边 |
| `color.bg-page` | `#F8FAFC` | `--color-bg` | 页面底色、消息区底色 |
| `color.bg-surface` | `#FFFFFF` | `--color-surface` | 卡片、侧栏、输入框底色 |

### 1.2 派生色（当前存在于画板，尚未登记为令牌）

实现时先用下面列出的值，后续统一收敛进令牌集；**不要**再新增同义色。

| 值 | 用途 | 建议令牌名 |
|---|---|---|
| `#94A3B8` | 未选中图标、占位文字、弱提示 | `color.text-muted` |
| `#CBD5E1` | 次级图标、禁用 | `color.icon-disabled` |
| `#F1F5F9` | 浅底标签、输入区背景 | `color.bg-subtle` |
| `#EFF6FF` | 选中行底色 | `color.bg-selected` |
| `#BFDBFE` | 选中行描边 | `color.border-selected` |
| `#E9EEF4` | 卡片描边 | `color.border-card` |
| `#D8E0EA` | 控件描边（按钮、输入框） | `color.border-control` |
| `#ECFDF5` / `#15803D` | 正常徽章底 / 字 | `color.success-bg` / `-fg` |
| `#FFFBEB` / `#B45309` | 未配置徽章底 / 字 | `color.warning-bg` / `-fg` |
| `#FEF2F2` / `#B91C1C` | 异常徽章底 / 字 | `color.danger-bg` / `-fg` |

### 1.3 状态色语义

| 状态 | 前景 | 底色 | 是否必须配文字 |
|---|---|---|---|
| 正常 | `#15803D` | `#ECFDF5` | 是 |
| 未配置 | `#B45309` | `#FFFBEB` | 是 |
| 异常 / 失败 | `#B91C1C` | `#FEF2F2` | 是 |
| 扫描中 / 进行中 | `#64748B` | `#F1F5F9` | 是 |
| 禁用 | `#94A3B8` | `transparent` | 是 |

> 硬规则（来自 `01-ia.md` §6）：**不允许只用颜色传达状态**，每个状态徽章必须带文字。

## 2. 字号与字体

### 2.1 字号阶梯

| 令牌 | 值 | 用途 |
|---|---|---|
| `font.2xl` | `28px` | 营销页大标题（当前未使用） |
| `font.xl` | `20px` | 页面级标题 |
| `font.lg` | `16px` | 面板标题、品牌名 |
| `font.md` | `14px` | 正文、列表主文案、按钮 |
| `font.sm` | `12px` | 辅助说明、次要按钮 |
| — | `11px` | 徽章、元信息、路径 |
| — | `10px` | 徽章内文字、页脚提示 |

### 2.2 字重

允许：`400`（正文）/ `600`（强调、按钮）/ `700`（标题）。
**禁止 `500`**：Penpot 默认字体不提供该字重，设置会直接报错；前端也不要用，避免与设计稿不一致。

### 2.3 行高

| 场景 | 值 |
|---|---|
| 标题 | `1.2`–`1.3` |
| 界面文本 | `1.4` |
| 多行正文 | `1.6`–`1.65` |

### 2.4 字体栈

```css
--font-sans: system-ui, -apple-system, "Segoe UI", "PingFang SC",
             "Microsoft YaHei", sans-serif;
--font-mono: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
```

路径、模型标识等技术字符串使用 `--font-mono`。

## 3. 间距

| 令牌 | 值 | 典型用途 |
|---|---|---|
| `space.xs` | `4px` | 图标与文字、徽章内边距 |
| `space.sm` | `8px` | 行内元素间距、按钮组 |
| `space.md` | `12px` | 列表项内边距、卡片内行距 |
| `space.lg` | `16px` | 面板内边距、卡片间距 |
| `space.xl` | `24px` | 主区域左右留白 |
| `space.2xl` | `32px` | 模块之间 |

## 4. 圆角

| 令牌 | 值 | 用途 |
|---|---|---|
| `radius.sm` | `6px` | 小标签、图标按钮（24px 级） |
| `radius.md` | `8px` | 按钮、输入内部块 |
| `radius.lg` | `12px` | 消息气泡、输入框、卡片 |
| `radius.xl` | `16px` | 大卡片 |
| — | `7px` | 品牌 Logo 方块（24px 专用） |
| — | `999px` | 状态徽章（胶囊） |

## 5. 阴影

| 名称 | 值 | 用途 |
|---|---|---|
| `shadow.card` | `0 10px 28px rgba(15,23,42,0.10)` | 卡片、浮层 |
| `shadow.none` | `none` | 面板、列表项（靠描边区分层级） |

## 6. 动效

首版画板是静态的，动效规则如下（数值为实现约定，需在实现卡落地时复核）：

| 场景 | 时长 | 缓动 |
|---|---|---|
| hover / 颜色变化 | `120ms` | `ease-out` |
| 侧栏收起 / 展开 | `200ms` | `cubic-bezier(0.2, 0, 0, 1)` |
| 面板淡入 | `160ms` | `ease-out` |

`prefers-reduced-motion: reduce` 时全部降为 `0ms`。

## 7. 布局尺寸

| 区域 | 默认态 | 收起态 |
|---|---|---|
| 设计基准宽度 | `1440px` | `1440px` |
| 主导航 | `232px` | `232px` |
| 列表面板（工具 + 会话） | `300px` | `0`（隐藏） |
| 主内容 | `908px`（fill） | `1208px`（fill） |
| 工具头高度 | `65px` | `65px` |
| 上下文条高度 | `48px` | `48px` |
| 输入区高度 | `≈122px` | `≈122px` |

实现必须让主内容宽度为 **fill**，收起时自动撑开，不得写死 `908px`。

## 8. 亮 / 暗模式策略

- **首版只交付亮色模式**：不实现暗色主题，也不放主题切换入口（按 `01-ia.md` §7「暂不可用时不显示空壳入口」）。
- **令牌层同时支持双套**：上面所有颜色都以 CSS 变量形式定义，暗色模式落地时只替换 `:root[data-theme="dark"]` 下的变量值，不改组件。
- 新增颜色必须先进本文件，再在组件里以变量引用；禁止在 `.vue` 里出现裸十六进制色值（`#` 开头），品牌图形除外。

## 9. 可直接使用的 CSS 变量

```css
:root {
  --color-primary: #2563EB;
  --color-primary-hover: #1D4ED8;
  --color-accent: #06B6D4;
  --color-warning: #F59E0B;
  --color-danger: #DC2626;
  --color-success: #16A34A;
  --color-text: #0F172A;
  --color-text-secondary: #64748B;
  --color-text-muted: #94A3B8;
  --color-border: #E2E8F0;
  --color-border-control: #D8E0EA;
  --color-bg: #F8FAFC;
  --color-surface: #FFFFFF;
  --color-bg-subtle: #F1F5F9;
  --color-bg-selected: #EFF6FF;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  --space-2xl: 32px;

  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  --shadow-card: 0 10px 28px rgba(15, 23, 42, 0.1);

  --font-sans: system-ui, -apple-system, "Segoe UI", "PingFang SC",
               "Microsoft YaHei", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
}
```