<script setup lang="ts">
import { ref, watch } from 'vue'

import { ApiError } from '../api/client'
import { checkProfileHealth } from '../api/profile-health'
import type { HealthCheckResponse, HealthCheckStatus } from '../api/profile-health'
import type { ModelEntry } from '../api/profiles'

const props = defineProps<{
  profileId: string
  profileName: string
  models: ModelEntry[]
}>()

const selectedModel = ref('')
const loading = ref(false)
const result = ref<HealthCheckResponse | null>(null)
const error = ref<string | null>(null)

const statusLabels: Record<HealthCheckStatus, string> = {
  CONNECTED: '连接成功',
  INVALID_CREDENTIALS: '密钥无效',
  INVALID_ADDRESS: '地址错误',
  MODEL_NOT_FOUND: '模型不存在',
  TIMEOUT: '请求超时',
  RATE_LIMITED: '请求受限',
  SECRET_MISSING: '密钥缺失',
  SECRET_STORE_ERROR: '密钥存储异常',
  MODEL_REQUIRED: '需要模型',
  UNKNOWN: '未知错误',
}

watch(
  () => props.models.map((model) => model.id),
  (modelIds) => {
    if (!modelIds.includes(selectedModel.value)) {
      selectedModel.value = modelIds[0] ?? ''
    }
  },
  { immediate: true },
)

async function runHealthCheck(): Promise<void> {
  if (loading.value || selectedModel.value === '') {
    return
  }
  loading.value = true
  result.value = null
  error.value = null
  try {
    result.value = await checkProfileHealth(props.profileId, {
      model: selectedModel.value,
    })
  } catch (caught) {
    error.value =
      caught instanceof ApiError ? caught.message : '体检请求失败，请检查后端服务后重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="health-check" :aria-label="`体检档案 ${props.profileName}`">
    <p class="health-check__notice">
      体检会向供应商发起一次真实请求，可能产生少量费用；不会发送聊天内容。
    </p>

    <div class="health-check__controls">
      <label :for="`health-model-${props.profileId}`">
        体检模型
      </label>
      <select
        :id="`health-model-${props.profileId}`"
        v-model="selectedModel"
        :disabled="loading || props.models.length === 0"
      >
        <option v-if="props.models.length === 0" value="">尚无可选模型</option>
        <option v-for="model in props.models" :key="model.id" :value="model.id">
          {{ model.display_name ? `${model.display_name}（${model.id}）` : model.id }}
        </option>
      </select>
      <button
        type="button"
        :disabled="loading || selectedModel === ''"
        :aria-label="`体检档案 ${props.profileName}`"
        @click="runHealthCheck"
      >
        {{ loading ? '体检中…' : '体检' }}
      </button>
    </div>
    <p v-if="props.models.length === 0" class="health-check__empty" role="status">
      尚无模型，请先编辑档案并添加模型后再体检。
    </p>

    <p v-if="loading" class="health-check__loading" role="status">
      正在检查地址、凭证与模型…
    </p>
    <p v-if="error !== null" class="health-check__error" role="alert">{{ error }}</p>
    <p
      v-if="result !== null"
      class="health-check__result"
      :class="{ 'health-check__result--success': result.status === 'CONNECTED' }"
      role="status"
    >
      {{ statusLabels[result.status] }}：{{ result.message }}
      <span v-if="result.duration_ms !== null">（耗时 {{ result.duration_ms }} ms）</span>
    </p>
  </section>
</template>

<style scoped>
.health-check {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  border-top: 1px solid var(--color-border);
  padding-top: var(--space-2);
}

.health-check__notice,
.health-check__empty,
.health-check__loading,
.health-check__result,
.health-check__error {
  margin: 0;
  overflow-wrap: anywhere;
  font-size: var(--font-size-sm);
}

.health-check__notice,
.health-check__empty,
.health-check__loading {
  color: var(--color-text-secondary);
}

.health-check__error {
  color: var(--color-danger);
}

.health-check__result--success {
  color: var(--status-ok-fg);
}

.health-check__controls {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.health-check__controls select {
  min-width: 0;
  max-width: 100%;
}

.health-check__controls button {
  white-space: nowrap;
}

@media (max-width: 480px) {
  .health-check__controls {
    grid-template-columns: minmax(0, 1fr);
  }

  .health-check__controls button {
    width: 100%;
  }
}
</style>
