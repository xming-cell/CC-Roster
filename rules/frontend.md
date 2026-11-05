# 前端规则

技术栈：Vue 3 · Vite · TS · Pinia · pnpm。参考实现：`frontend/src/App.vue`。

## 请求
- 所有 HTTP 请求走 `src/api/`，**组件里禁止直接 `fetch` / `axios`**。
- `src/api/` 里只做「拼 URL + 类型标注 + 错误归一」，返回值必须有显式类型，禁止 `any`。
- 后端错误统一 `{code, message}`，前端在 `src/api/` 里转成 `ApiError` 再抛，组件只处理 `ApiError`。

## 状态与逻辑
- 跨组件共享状态进 Pinia（`src/stores/`），单组件状态留在组件里，别为了「统一」把局部状态塞进 store。
- 可复用的纯逻辑进 `src/utils/`，可复用的有状态逻辑进 `src/composables/`（`useXxx`）。
- 组件内禁止写业务校验规则的副本——规则以后端为准，前端只做即时提示。

## 组件
- 单文件超过 ~150 行就考虑拆子组件或抽 composable。
- props / emits 必须显式声明类型（`defineProps<Props>()`），禁止 `defineProps()` 裸用。
- 所有 `v-for` 必须有稳定 `:key`，禁止用 index 当 key（列表会重排时）。

## 禁止
- `as any`、`// @ts-ignore`、`// @ts-expect-error`（`scripts/guards.py` 会拦）。
- `.skip` / `.only` 留在提交里（`.only` 会让其余测试静默不跑）。
- 内联 `style` 承载布局；样式写在 `<style scoped>`。