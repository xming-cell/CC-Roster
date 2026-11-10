<script setup lang="ts">
import type { ToolView } from '../api/tools'
import ToolStatusBadge from './ToolStatusBadge.vue'

defineProps<{
  tool: ToolView | null
  loading: boolean
  error: string | null
  embedded?: boolean
}>()

function thirdPartyLabel(value: boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return '未知'
  }
  return value ? '是' : '否'
}

function secretLabel(tool: ToolView): string {
  if (!tool.has_secret) {
    return '未配置'
  }
  return tool.secret_preview ?? '****'
}

function formatLastModified(value: string | null): string {
  if (value === null) {
    return '未知'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('zh-CN', { hour12: false })
}
</script>

<template>
  <section
    class="detail"
    :class="{ 'detail--embedded': embedded }"
    :aria-label="embedded ? 'AI 详情' : undefined"
    :aria-labelledby="embedded ? undefined : 'tool-detail-title'"
  >
    <h2 v-if="!embedded" id="tool-detail-title">工具详情</h2>

    <p v-if="loading" role="status">正在读取详情…</p>
    <p v-else-if="error !== null" role="alert">{{ error }}</p>
    <template v-else-if="tool !== null">
      <h3 v-if="!embedded">{{ tool.display_name }}</h3>
      <dl class="detail__fields">
        <dt>状态</dt>
        <dd><ToolStatusBadge :status="tool.status" /></dd>
        <dt>供应商</dt>
        <dd>{{ tool.provider ?? '未知' }}</dd>
        <dt>模型</dt>
        <dd>{{ tool.model ?? '未知' }}</dd>
        <dt>接口地址</dt>
        <dd>{{ tool.base_url ?? '未配置' }}</dd>
        <dt>第三方中转</dt>
        <dd>{{ thirdPartyLabel(tool.is_third_party) }}</dd>
        <dt>密钥</dt>
        <dd>{{ secretLabel(tool) }}</dd>
        <dt>最后修改时间</dt>
        <dd>{{ formatLastModified(tool.last_modified) }}</dd>
        <dt>配置路径</dt>
        <dd class="detail__path">{{ tool.config_path ?? '未知' }}</dd>
      </dl>

      <div v-if="tool.warnings.length > 0" class="detail__warnings" role="alert">
        <h4>警告</h4>
        <ul>
          <li v-for="warning in tool.warnings" :key="`${warning.code}-${warning.message}`">
            {{ warning.code }}: {{ warning.message }}
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

<style scoped>
.detail {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.detail--embedded {
  border: 0;
  padding: 0;
}

.detail__fields {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: var(--space-2) var(--space-4);
  margin: 0;
}

.detail__fields dt {
  color: var(--color-text-secondary);
}

.detail__fields dd {
  margin: 0;
}

.detail__path {
  overflow-wrap: anywhere;
}

.detail__warnings {
  margin-top: var(--space-4);
  color: var(--color-danger);
}
</style>