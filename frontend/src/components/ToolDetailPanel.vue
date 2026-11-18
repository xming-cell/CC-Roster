<script setup lang="ts">
import type { ToolView } from '../api/tools'
import {
  baseUrlLabel,
  configurationLabel,
  configPathLabel,
  formatLastModified,
  installationLabel,
  modelLabel,
  providerLabel,
  secretLabel,
  thirdPartyLabel,
  versionLabel,
} from '../utils/toolDisplay'
import ToolStatusBadge from './ToolStatusBadge.vue'

defineProps<{
  tool: ToolView | null
  loading: boolean
  error: string | null
  selectedToolId: string | null
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <section class="detail" role="region" aria-labelledby="tool-detail-title">
    <header class="detail__header">
      <h2 id="tool-detail-title" class="detail__heading">工具详情</h2>
    </header>

    <div v-if="selectedToolId === null" class="detail__state">
      <h3 class="detail__state-title">尚未选择工具</h3>
      <p class="detail__state-text">从左侧工具列表选择一项，查看安装、配置、供应商与模型信息。</p>
    </div>

    <div v-else-if="loading" class="detail__state" role="status">
      <p class="detail__state-text">正在读取详情…</p>
      <div class="detail-skeleton" aria-hidden="true">
        <span v-for="row in 4" :key="row" class="detail-skeleton__line"></span>
      </div>
    </div>

    <div v-else-if="error" class="detail__state detail__state--error" role="alert">
      <h3 class="detail__state-title">详情读取失败</h3>
      <p class="detail__state-text">{{ error }}</p>
      <p class="detail__state-hint">左侧列表仍可使用，可稍后重试或选择其他工具。</p>
      <button class="button button--secondary" type="button" @click="$emit('retry')">
        重新读取
      </button>
    </div>

    <template v-else-if="tool">
      <div class="detail__title-row">
        <h3 class="detail__name">{{ tool.display_name }}</h3>
        <ToolStatusBadge :status="tool.status" />
      </div>

      <dl class="detail__fields">
        <dt>安装状态</dt>
        <dd class="detail__value">{{ installationLabel(tool) }}</dd>
        <dt>配置状态</dt>
        <dd class="detail__value">{{ configurationLabel(tool) }}</dd>
        <dt>供应商</dt>
        <dd class="detail__value">{{ providerLabel(tool) }}</dd>
        <dt>模型</dt>
        <dd class="detail__value detail__value--mono">{{ modelLabel(tool) }}</dd>
        <dt>接口地址</dt>
        <dd class="detail__value detail__value--mono">{{ baseUrlLabel(tool) }}</dd>
        <dt>第三方中转</dt>
        <dd class="detail__value">{{ thirdPartyLabel(tool.is_third_party) }}</dd>
        <dt>密钥</dt>
        <dd class="detail__value detail__value--mono">{{ secretLabel(tool) }}</dd>
        <dt>配置路径</dt>
        <dd class="detail__value detail__value--mono">{{ configPathLabel(tool) }}</dd>
        <dt>最后修改时间</dt>
        <dd class="detail__value">{{ formatLastModified(tool.last_modified) }}</dd>
        <dt>版本</dt>
        <dd class="detail__value detail__value--mono">{{ versionLabel(tool) }}</dd>
      </dl>

      <section
        v-if="tool.warnings.length > 0"
        class="detail__warnings"
        aria-labelledby="tool-warning-title"
      >
        <h4 id="tool-warning-title" class="detail__warnings-title">警告</h4>
        <ul class="detail__warning-list">
          <li v-for="warning in tool.warnings" :key="`${warning.code}-${warning.message}`">
            {{ warning.code }}: {{ warning.message }}
          </li>
        </ul>
      </section>
    </template>
  </section>
</template>

<style scoped>
.detail {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-xl);
  background: var(--color-bg);
}

.detail__header {
  margin-bottom: var(--space-lg);
}

.detail__heading {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: var(--line-height-tight);
}

.detail__state {
  max-width: 600px;
  padding: var(--space-xl);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.detail__state--error {
  border-color: var(--color-danger-bg);
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.detail__state-title {
  margin: 0 0 var(--space-sm);
  font-size: var(--font-size-lg);
  font-weight: 600;
  line-height: var(--line-height-tight);
}

.detail__state-text {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  line-height: var(--line-height-relaxed);
  overflow-wrap: anywhere;
}

.detail__state--error .detail__state-text {
  color: var(--color-danger-fg);
}

.detail__state-hint {
  margin: var(--space-sm) 0 var(--space-lg);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.detail__title-row {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  min-width: 0;
  margin-bottom: var(--space-lg);
}

.detail__name {
  min-width: 0;
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: var(--line-height-tight);
  overflow-wrap: anywhere;
}

.detail__fields {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 10px 20px;
  margin: 0;
  padding: var(--space-lg);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.detail__fields dt {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.detail__fields dd {
  margin: 0;
  color: var(--color-text);
  font-size: var(--font-size-md);
  overflow-wrap: anywhere;
}

.detail__value--mono {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.detail__warnings {
  margin-top: var(--space-lg);
  padding: var(--space-md) 14px;
  border-radius: var(--radius-md);
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.detail__warnings-title {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.detail__warning-list {
  margin: var(--space-xs) 0 0;
  padding-left: 18px;
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.detail-skeleton {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: var(--space-lg);
}

.detail-skeleton__line {
  width: 100%;
  height: 12px;
  border-radius: 999px;
  background: var(--color-bg-subtle);
  animation: detail-pulse 1.2s ease-in-out infinite;
}

.detail-skeleton__line:nth-child(2) {
  width: 78%;
}

.detail-skeleton__line:nth-child(3) {
  width: 88%;
}

.detail-skeleton__line:nth-child(4) {
  width: 62%;
}

@keyframes detail-pulse {
  0%,
  100% {
    opacity: 0.55;
  }

  50% {
    opacity: 1;
  }
}

@media (max-width: 560px) {
  .detail {
    padding: var(--space-lg);
  }

  .detail__fields {
    grid-template-columns: minmax(0, 1fr);
  }

  .detail__fields dt {
    margin-top: var(--space-xs);
  }
}
</style>
