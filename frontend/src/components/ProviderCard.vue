<script setup lang="ts">
import { computed } from 'vue'

import type { HealthCheckResponse, ProfileView } from '../api/profiles'
import type { ProviderItem } from '../stores/profiles'
import {
  formatDateTime,
  healthStatusLabel,
  healthTone,
  protocolLabel,
  secretPreviewLabel,
  secretStatusLabel,
} from '../utils/profileDisplay'

const props = defineProps<{
  item: ProviderItem
  healthResult: HealthCheckResponse | undefined
  healthLoading: boolean
  healthError: string | undefined
  busy: boolean
}>()

const emit = defineEmits<{
  health: [profileId: string]
  edit: [profile: ProfileView]
  copy: [profileId: string]
  remove: [profileId: string]
  delete: [profile: ProfileView]
}>()

const profile = computed(() => props.item.profile)
const binding = computed(() => props.item.binding)
const visibleModels = computed(() => profile.value.models.slice(0, 3))
const remainingModels = computed(() => Math.max(0, profile.value.models.length - 3))
const secretWarnings = computed(() =>
  profile.value.warnings.filter(
    (warning) => warning.code === 'SECRET_MISSING' || warning.code === 'SECRET_STORE_ERROR',
  ),
)
const resultTone = computed(() => {
  const result = props.healthResult
  return result === undefined ? 'neutral' : healthTone(result.status)
})
const durationLabel = computed(() => {
  const duration = props.healthResult?.duration_ms
  return duration === null || duration === undefined ? '未发起请求' : duration + ' ms'
})
</script>

<template>
  <article class="provider-card" :aria-labelledby="'provider-name-' + profile.id">
    <header class="provider-card__header">
      <div class="provider-card__title-row">
        <h3 :id="'provider-name-' + profile.id" class="provider-card__name">{{ profile.name }}</h3>
        <span
          class="provider-card__badge"
          :class="binding.active ? 'provider-card__badge--active' : 'provider-card__badge--inactive'"
        >
          <span v-if="binding.active" class="provider-card__dot" aria-hidden="true"></span>
          {{ binding.active ? '已启用' : '未启用' }}
        </span>
        <span class="provider-card__protocol">{{ protocolLabel(profile.protocol) }}</span>
      </div>
      <p class="provider-card__bound">绑定于 {{ formatDateTime(binding.bound_at) }}</p>
    </header>

    <dl class="provider-card__fields">
      <div class="provider-card__field provider-card__field--wide">
        <dt>接口地址</dt>
        <dd class="provider-card__mono">{{ profile.base_url }}</dd>
      </div>
      <div class="provider-card__field provider-card__field--wide">
        <dt>模型</dt>
        <dd class="provider-card__models">
          <span v-for="model in visibleModels" :key="model.id" class="provider-card__model">
            {{ model.id }}
          </span>
          <span v-if="remainingModels > 0" class="provider-card__model">+{{ remainingModels }}</span>
          <span v-if="profile.models.length === 0" class="provider-card__muted">未设置模型</span>
        </dd>
      </div>
      <div class="provider-card__field">
        <dt>密钥</dt>
        <dd>
          <span
            class="provider-card__secret"
            :class="{ 'provider-card__secret--missing': !profile.has_secret }"
          >
            {{ secretStatusLabel(profile) }}
          </span>
          <span class="provider-card__secret-preview">{{ secretPreviewLabel(profile) }}</span>
        </dd>
      </div>
    </dl>

    <div v-if="secretWarnings.length > 0" class="provider-card__warnings" role="status">
      <p v-for="warning in secretWarnings" :key="warning.code + warning.message">
        {{ warning.message }}
      </p>
    </div>

    <section class="provider-card__health" aria-label="健康检查结果">
      <div v-if="healthLoading" class="provider-card__health-state" role="status">
        <span class="provider-card__health-label">正在检测…</span>
        <span class="provider-card__muted">请稍候，检测不会修改供应商配置。</span>
      </div>
      <div v-else-if="healthError" class="provider-card__health-state provider-card__health-state--danger" role="alert">
        <span class="provider-card__health-label">检测失败</span>
        <span>{{ healthError }}</span>
      </div>
      <div v-else-if="healthResult" class="provider-card__health-state" :class="'provider-card__health-state--' + resultTone">
        <span class="provider-card__health-label">{{ healthStatusLabel(healthResult.status) }}</span>
        <span>{{ healthResult.message }}</span>
        <span class="provider-card__health-meta">
          {{ durationLabel }} · {{ healthResult.model ?? '未选择模型' }} · {{ formatDateTime(healthResult.checked_at) }}
        </span>
      </div>
      <div v-else class="provider-card__health-state provider-card__health-state--neutral">
        <span class="provider-card__health-label">尚未检测</span>
        <span class="provider-card__muted">运行健康检查，确认地址、密钥和模型是否可用。</span>
      </div>
    </section>

    <footer class="provider-card__actions">
      <button
        class="provider-card__action provider-card__action--primary"
        type="button"
        :disabled="healthLoading || busy"
        :aria-label="'健康检查 ' + profile.name"
        @click="emit('health', profile.id)"
      >
        {{ healthLoading ? '检测中…' : '健康检查' }}
      </button>
      <button class="provider-card__action" type="button" :disabled="busy" :aria-label="'编辑 ' + profile.name" @click="emit('edit', profile)">
        编辑
      </button>
      <button class="provider-card__action" type="button" :disabled="busy" :aria-label="'复制 ' + profile.name" @click="emit('copy', profile.id)">
        复制
      </button>
      <button class="provider-card__action" type="button" :disabled="busy" :aria-label="'从工具移除 ' + profile.name" @click="emit('remove', profile.id)">
        从工具移除
      </button>
      <span class="provider-card__action-divider" aria-hidden="true"></span>
      <button
        class="provider-card__action provider-card__action--danger"
        type="button"
        :disabled="busy"
        :aria-label="'删除 ' + profile.name"
        @click="emit('delete', profile)"
      >
        删除
      </button>
    </footer>
  </article>
</template>

<style scoped>
.provider-card {
  padding: var(--space-lg);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.provider-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-md);
}

.provider-card__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm);
  min-width: 0;
}

.provider-card__name {
  min-width: 0;
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 700;
  line-height: var(--line-height-tight);
  overflow-wrap: anywhere;
}

.provider-card__badge,
.provider-card__protocol {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: 2px 7px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}

.provider-card__badge--active {
  background: var(--color-success-bg);
  color: var(--color-success-fg);
}

.provider-card__badge--inactive {
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
}

.provider-card__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
}

.provider-card__protocol {
  background: var(--color-bg-subtle);
  color: var(--color-info-fg);
  font-weight: 400;
}

.provider-card__bound {
  flex: none;
  margin: 2px 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.provider-card__fields {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: var(--space-sm) var(--space-lg);
  margin: var(--space-md) 0 0;
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border-card);
}

.provider-card__field {
  min-width: 0;
}

.provider-card__field--wide {
  grid-column: 1 / -1;
}

.provider-card__field dt {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.provider-card__field dd {
  margin: 2px 0 0;
  color: var(--color-text);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.provider-card__mono {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.provider-card__models {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
}

.provider-card__model {
  max-width: 100%;
  padding: 2px 7px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-subtle);
  color: var(--color-info-fg);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.provider-card__muted {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.provider-card__secret {
  margin-right: var(--space-sm);
  color: var(--color-success-fg);
  font-weight: 600;
}

.provider-card__secret--missing {
  color: var(--color-warning-fg);
}

.provider-card__secret-preview {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.provider-card__warnings {
  margin-top: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
  font-size: var(--font-size-xs);
}

.provider-card__warnings p {
  margin: 0;
}

.provider-card__health {
  margin-top: var(--space-md);
}

.provider-card__health-state {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.provider-card__health-state--success {
  background: var(--color-success-bg);
  color: var(--color-success-fg);
}

.provider-card__health-state--warning {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.provider-card__health-state--danger {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.provider-card__health-state--neutral {
  background: var(--color-bg);
}

.provider-card__health-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.provider-card__health-meta {
  color: inherit;
  opacity: 0.82;
}

.provider-card__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-xs);
  margin-top: var(--space-md);
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border-card);
}

.provider-card__action {
  padding: 5px 7px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
}

.provider-card__action:hover:not(:disabled) {
  background: var(--color-bg-subtle);
}

.provider-card__action:disabled {
  color: var(--color-text-muted);
  cursor: not-allowed;
}

.provider-card__action--primary {
  padding: 6px 12px;
  border-color: var(--color-border-control);
  background: var(--color-surface);
  color: var(--color-text);
}

.provider-card__action--danger {
  color: var(--color-danger);
}

.provider-card__action-divider {
  width: 1px;
  height: 18px;
  margin: 0 var(--space-xs);
  background: var(--color-border);
}

@media (max-width: 620px) {
  .provider-card__header {
    flex-direction: column;
  }

  .provider-card__fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
