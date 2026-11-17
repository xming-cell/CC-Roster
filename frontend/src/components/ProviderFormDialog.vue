<script setup lang="ts">
import { computed, ref } from 'vue'

import type {
  ModelEntry,
  ProfileCreateInput,
  ProfileProtocol,
  ProfileUpdateInput,
  ProfileView,
} from '../api/profiles'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  mode: 'create' | 'edit'
  toolName: string
  profile: ProfileView | null
  busy: boolean
  error: string | null
}>()

const emit = defineEmits<{
  submit: [payload: ProfileCreateInput | ProfileUpdateInput]
  close: []
}>()

const name = ref(props.profile?.name ?? '')
const protocol = ref<ProfileProtocol>(props.profile?.protocol ?? 'anthropic')
const baseUrl = ref(props.profile?.base_url ?? '')
const modelsText = ref(props.profile?.models.map((model) => model.id).join('\n') ?? '')
const secret = ref('')
const clearSecret = ref(false)
const localError = ref<string | null>(null)

const title = computed(() => (props.mode === 'create' ? '新增供应商' : '编辑供应商'))
const canClearSecret = computed(() => props.mode === 'edit' && props.profile?.has_secret === true)
const submitLabel = computed(() => {
  if (props.busy) {
    return '保存中…'
  }
  return props.mode === 'create' ? '创建并绑定' : '保存修改'
})

function buildModels(): ModelEntry[] {
  const previous = new Map((props.profile?.models ?? []).map((model) => [model.id, model]))
  return modelsText.value
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((id) => ({ id, display_name: previous.get(id)?.display_name ?? null }))
}

function handleSubmit(): void {
  localError.value = null
  const normalizedName = name.value.trim()
  const normalizedBaseUrl = baseUrl.value.trim()
  if (normalizedName.length === 0) {
    localError.value = '请填写供应商名称'
    return
  }
  if (!/^https?:\/\//i.test(normalizedBaseUrl)) {
    localError.value = '接口地址必须是 http 或 https 绝对地址'
    return
  }

  const models = buildModels()
  if (props.mode === 'create') {
    emit('submit', {
      name: normalizedName,
      protocol: protocol.value,
      base_url: normalizedBaseUrl,
      models,
      secret: secret.value.trim().length > 0 ? secret.value.trim() : null,
    })
    return
  }

  const payload: ProfileUpdateInput = {
    name: normalizedName,
    protocol: protocol.value,
    base_url: normalizedBaseUrl,
    models,
  }
  if (clearSecret.value) {
    payload.secret = null
  } else if (secret.value.trim().length > 0) {
    payload.secret = secret.value.trim()
  }
  emit('submit', payload)
}
</script>

<template>
  <ModalShell labelled-by="provider-form-title" @close="emit('close')">
    <form class="provider-form" @submit.prevent="handleSubmit">
      <header class="provider-form__header">
        <div>
          <h2 id="provider-form-title" class="provider-form__title">{{ title }}</h2>
          <p class="provider-form__subtitle">绑定到 {{ toolName }} · 只修改供应商数据，不会写入工具配置</p>
        </div>
        <button class="icon-button" type="button" aria-label="关闭表单" :disabled="busy" @click="emit('close')">
          <svg class="provider-form__close" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
            <path d="m4 4 8 8M12 4l-8 8" />
          </svg>
        </button>
      </header>

      <div v-if="localError || error" class="provider-form__alert" role="alert">
        {{ localError ?? error }}
      </div>

      <div class="provider-form__body">
        <label class="field">
          <span class="field__label">名称</span>
          <input
            v-model="name"
            class="field__control"
            type="text"
            maxlength="80"
            required
            autocomplete="off"
            :disabled="busy"
          />
        </label>

        <label class="field">
          <span class="field__label">协议</span>
          <select v-model="protocol" class="field__control" :disabled="busy">
            <option value="anthropic">Anthropic</option>
            <option value="openai">OpenAI 兼容</option>
          </select>
        </label>

        <label class="field">
          <span class="field__label">接口地址</span>
          <input
            v-model="baseUrl"
            class="field__control field__control--mono"
            type="url"
            maxlength="2048"
            required
            placeholder="https://api.example.com/v1"
            autocomplete="off"
            :disabled="busy"
          />
        </label>

        <label class="field">
          <span class="field__label">模型清单</span>
          <textarea
            v-model="modelsText"
            class="field__control field__control--mono field__control--textarea"
            rows="4"
            placeholder="claude-sonnet-4-5&#10;claude-opus-4-5"
            :disabled="busy"
          ></textarea>
          <span class="field__hint">每行一个模型标识；可以留空，健康检查会提示需要模型。</span>
        </label>

        <label class="field">
          <span class="field__label">密钥</span>
          <input
            v-model="secret"
            class="field__control field__control--mono"
            type="password"
            autocomplete="new-password"
            :placeholder="
              mode === 'create'
                ? '留空表示暂不设置'
                : '留空表示保持原密钥'
            "
            :disabled="busy || clearSecret"
          />
          <span class="field__hint">密钥只保存在本机；界面不会展示明文。</span>
        </label>

        <label v-if="canClearSecret" class="provider-form__check">
          <input v-model="clearSecret" type="checkbox" :disabled="busy" />
          <span>清除已保存的密钥</span>
        </label>
      </div>

      <footer class="provider-form__footer">
        <button class="button button--secondary" type="button" :disabled="busy" @click="emit('close')">
          取消
        </button>
        <button class="button" type="submit" :disabled="busy">{{ submitLabel }}</button>
      </footer>
    </form>
  </ModalShell>
</template>

<style scoped>
.provider-form {
  padding: var(--space-xl);
}

.provider-form__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-lg);
  margin-bottom: var(--space-lg);
}

.provider-form__title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: var(--line-height-tight);
}

.provider-form__subtitle {
  margin: var(--space-xs) 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.provider-form__close {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-width: 1.8;
}

.provider-form__alert {
  margin-bottom: var(--space-lg);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.provider-form__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  color: var(--color-text);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.field__control {
  width: 100%;
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text);
  font: inherit;
  font-size: var(--font-size-md);
}

.field__control:disabled {
  background: var(--color-bg-subtle);
  color: var(--color-text-muted);
}

.field__control--mono {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.field__control--textarea {
  min-height: 92px;
  resize: vertical;
}

.field__hint {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.provider-form__check {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.provider-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  margin-top: var(--space-xl);
}
</style>
