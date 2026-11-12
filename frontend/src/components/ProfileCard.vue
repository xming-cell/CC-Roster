<script setup lang="ts">
import type { ProfileView } from '../api/profiles'
import ProfileHealthCheck from './ProfileHealthCheck.vue'
import {
  protocolLabel,
  secretBackendLabel,
  usedByLabel,
  warningLabel,
} from '../utils/profiles'

const props = defineProps<{ profile: ProfileView }>()

const emit = defineEmits<{
  edit: []
  copy: []
  delete: []
}>()

function usageText(profile: ProfileView): string {
  return profile.used_by.length === 0 ? '未被任何工具使用' : usedByLabel(profile.used_by)
}
</script>

<template>
  <article class="card" :aria-label="`档案 ${props.profile.name}`">
    <header class="card__header">
      <h3 class="card__name">{{ props.profile.name }}</h3>
      <span class="card__protocol">{{ protocolLabel(props.profile.protocol) }}</span>
    </header>

    <dl class="card__fields">
      <dt>接口地址</dt>
      <dd class="card__url">{{ props.profile.base_url }}</dd>
      <dt>模型</dt>
      <dd>
        {{ props.profile.models.length === 0 ? '尚未添加模型' : `${props.profile.models.length} 个模型` }}
      </dd>
      <dt>密钥</dt>
      <dd>
        <span v-if="props.profile.warnings.length > 0" class="card__warning" role="alert">
          <span
            v-for="warning in props.profile.warnings"
            :key="`${warning.code}-${warning.message}`"
          >
            {{ warningLabel(warning.code) }}：{{ warning.message }}
          </span>
        </span>
        <span v-else-if="props.profile.has_secret">
          {{ props.profile.secret_preview ?? '****' }}（{{
            secretBackendLabel(props.profile.secret_backend)
          }}）
        </span>
        <span v-else>未设置密钥</span>
      </dd>
      <dt>占用工具</dt>
      <dd>{{ usageText(props.profile) }}</dd>
    </dl>

    <ProfileHealthCheck
      :profile-id="props.profile.id"
      :profile-name="props.profile.name"
      :models="props.profile.models"
    />

    <footer class="card__actions">
      <button
        type="button"
        :aria-label="`编辑档案 ${props.profile.name}`"
        @click="emit('edit')"
      >
        编辑
      </button>
      <button
        type="button"
        :aria-label="`复制档案 ${props.profile.name}`"
        @click="emit('copy')"
      >
        复制
      </button>
      <button
        type="button"
        class="card__delete"
        :aria-label="`删除档案 ${props.profile.name}`"
        @click="emit('delete')"
      >
        删除
      </button>
    </footer>
  </article>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
}

.card__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.card__name {
  margin: 0;
  font-size: var(--font-size-lg);
}

.card__protocol {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.card__fields {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: var(--space-1) var(--space-3);
  margin: 0;
}

.card__fields dt {
  color: var(--color-text-secondary);
}

.card__fields dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.card__url {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: var(--font-size-sm);
}

.card__warning {
  color: var(--color-danger);
}

.card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.card__delete {
  color: var(--color-danger);
}
</style>