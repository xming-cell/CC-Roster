<script setup lang="ts">
import { computed } from 'vue'

import type {
  HealthCheckResponse,
  ProfileWarning,
  SecretStoreStatus,
} from '../api/profiles'
import type { ToolView } from '../api/tools'
import type { ProviderItem } from '../stores/profiles'
import ProviderCard from './ProviderCard.vue'

const props = defineProps<{
  tool: ToolView | null
  items: ProviderItem[]
  loading: boolean
  loaded: boolean
  error: string | null
  secretStore: SecretStoreStatus | null
  warnings: ProfileWarning[]
  healthResults: Record<string, HealthCheckResponse>
  healthLoading: Record<string, boolean>
  healthErrors: Record<string, string>
  busyProfileId: string | null
}>()

const emit = defineEmits<{
  retry: []
  add: []
  health: [profileId: string]
  edit: [profile: ProviderItem['profile']]
  copy: [profileId: string]
  remove: [profileId: string]
  delete: [profile: ProviderItem['profile']]
}>()

const activeItem = computed(() => props.items.find((item) => item.binding.active) ?? null)
const secretConfigured = computed(() => props.items.filter((item) => item.profile.has_secret).length)
const secretStoreTone = computed(() => {
  const status = props.secretStore
  if (status?.backend === 'unavailable') {
    return 'danger'
  }
  if (status?.fallback === true) {
    return 'warning'
  }
  return null
})
</script>

<template>
  <section class="provider-list" role="region" aria-labelledby="provider-list-title">
    <h2 id="provider-list-title" class="sr-only">
      {{ tool?.display_name ?? '当前工具' }} 的供应商
    </h2>

    <div v-if="loaded" class="provider-summary" aria-label="供应商汇总">
      <div class="provider-summary__item">
        <span class="provider-summary__label">已绑定</span>
        <strong>{{ items.length }} 个</strong>
      </div>
      <span class="provider-summary__divider" aria-hidden="true"></span>
      <div class="provider-summary__item">
        <span class="provider-summary__label">当前启用</span>
        <span v-if="activeItem" class="provider-summary__active">
          <span class="provider-summary__dot" aria-hidden="true"></span>
          {{ activeItem.profile.name }}
        </span>
        <strong v-else>未启用</strong>
      </div>
      <span class="provider-summary__divider" aria-hidden="true"></span>
      <div class="provider-summary__item">
        <span class="provider-summary__label">密钥</span>
        <strong :class="{ 'provider-summary__value--warning': secretConfigured < items.length }">
          {{ secretConfigured }} / {{ items.length }} 已配置
        </strong>
      </div>
      <span class="provider-summary__spacer"></span>
      <span class="provider-summary__hint">按绑定顺序排列</span>
    </div>

    <div v-if="secretStoreTone" class="provider-list__banner" :class="'provider-list__banner--' + secretStoreTone" role="status">
      <strong>{{ secretStore?.backend === 'unavailable' ? '密钥存储不可用' : '密钥存储已降级' }}</strong>
      <span>
        {{ secretStore?.message ?? '供应商数据仍可查看，但密钥相关操作可能失败。' }}
      </span>
    </div>

    <div v-if="warnings.length > 0" class="provider-list__banner provider-list__banner--warning" role="status">
      <strong>供应商数据有降级提示</strong>
      <ul>
        <li v-for="warning in warnings" :key="warning.code + warning.message">{{ warning.message }}</li>
      </ul>
    </div>

    <div v-if="loading && !loaded" class="provider-list__skeleton" aria-hidden="true">
      <span v-for="row in 3" :key="row" class="provider-list__skeleton-card"></span>
    </div>

    <div v-else-if="error" class="provider-list__state provider-list__state--error" role="alert">
      <h3>供应商列表读取失败</h3>
      <p>{{ error }}</p>
      <p class="provider-list__hint">工具列表仍可使用，可稍后重试或选择其他工具。</p>
      <button class="button button--secondary" type="button" @click="emit('retry')">重试</button>
    </div>

    <div v-else-if="items.length === 0" class="provider-list__state">
      <h3>还没有绑定供应商</h3>
      <p>为 {{ tool?.display_name ?? '当前工具' }} 新增一个供应商，创建后会先以「未启用」状态绑定。</p>
      <button class="button" type="button" @click="emit('add')">新增供应商</button>
    </div>

    <ul v-else class="provider-list__items" aria-label="供应商列表">
      <li v-for="item in items" :key="item.profile.id">
        <ProviderCard
          :item="item"
          :health-result="healthResults[item.profile.id]"
          :health-loading="healthLoading[item.profile.id] === true"
          :health-error="healthErrors[item.profile.id]"
          :busy="busyProfileId === item.profile.id"
          @health="emit('health', $event)"
          @edit="emit('edit', $event)"
          @copy="emit('copy', $event)"
          @remove="emit('remove', $event)"
          @delete="emit('delete', $event)"
        />
      </li>
    </ul>
  </section>
</template>

<style scoped>
.provider-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-md);
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-xl);
}

.provider-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  font-size: var(--font-size-xs);
}

.provider-summary__item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.provider-summary__label {
  color: var(--color-text-muted);
}

.provider-summary__item strong {
  font-size: var(--font-size-sm);
}

.provider-summary__value--warning {
  color: var(--color-warning-fg);
}

.provider-summary__active {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  color: var(--color-success-fg);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.provider-summary__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
}

.provider-summary__divider {
  width: 1px;
  height: 20px;
  background: var(--color-border-card);
}

.provider-summary__spacer {
  flex: 1;
}

.provider-summary__hint {
  color: var(--color-text-muted);
}

.provider-list__banner {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.provider-list__banner--warning {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.provider-list__banner--danger {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.provider-list__banner ul {
  margin: 0;
  padding-left: 18px;
}

.provider-list__skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.provider-list__skeleton-card {
  height: 176px;
  border-radius: var(--radius-lg);
  background: var(--color-bg-subtle);
  animation: pulse 1.2s ease-in-out infinite;
}

.provider-list__state {
  padding: var(--space-xl);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.provider-list__state h3 {
  margin: 0 0 var(--space-xs);
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.provider-list__state p {
  margin: 0 0 var(--space-md);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  overflow-wrap: anywhere;
}

.provider-list__state--error {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.provider-list__state--error p {
  color: var(--color-danger-fg);
}

.provider-list__hint {
  color: var(--color-text-secondary);
}

.provider-list__items {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  margin: 0;
  padding: 0;
  list-style: none;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.55;
  }

  50% {
    opacity: 1;
  }
}
</style>
