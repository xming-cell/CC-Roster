<script setup lang="ts">
import { ref } from 'vue'

import type {
  ModelEntry,
  ProfileCreateInput,
  ProfileProtocol,
  ProfileView,
} from '../api/profiles'
import ModelEditor from './ModelEditor.vue'

const props = defineProps<{
  profile: ProfileView | null
  busy: boolean
  serverError: string | null
}>()

const emit = defineEmits<{
  submit: [payload: ProfileCreateInput]
  cancel: []
}>()

const name = ref(props.profile?.name ?? '')
const protocol = ref<ProfileProtocol>(props.profile?.protocol ?? 'anthropic')
const baseUrl = ref(props.profile?.base_url ?? '')
const models = ref<ModelEntry[]>([...(props.profile?.models ?? [])])
const secret = ref('')
const clearSecret = ref(false)

const isEditing = props.profile !== null
const hasStoredSecret =
  props.profile !== null &&
  (props.profile.has_secret || props.profile.secret_backend !== null)

function onSubmit(): void {
  const payload: ProfileCreateInput = {
    name: name.value,
    protocol: protocol.value,
    base_url: baseUrl.value,
    models: models.value,
  }
  if (isEditing) {
    if (clearSecret.value) {
      payload.secret = null
    } else if (secret.value.trim() !== '') {
      payload.secret = secret.value
    }
  } else if (secret.value.trim() !== '') {
    payload.secret = secret.value
  }
  emit('submit', payload)
}
</script>

<template>
  <form class="form" aria-label="档案表单" @submit.prevent="onSubmit">
    <header class="form__header">
      <h2>{{ isEditing ? '编辑档案' : '新建档案' }}</h2>
      <button type="button" :disabled="busy" @click="emit('cancel')">取消</button>
    </header>

    <p v-if="serverError !== null" class="form__error" role="alert">{{ serverError }}</p>

    <fieldset class="form__section">
      <legend>档案配置</legend>

      <label for="profile-name">名称</label>
      <input
        id="profile-name"
        v-model="name"
        type="text"
        required
        maxlength="80"
        autocomplete="off"
      />

      <label for="profile-protocol">协议</label>
      <select id="profile-protocol" v-model="protocol">
        <option value="anthropic">Anthropic</option>
        <option value="openai">OpenAI</option>
      </select>

      <label for="profile-base-url">接口地址</label>
      <input
        id="profile-base-url"
        v-model="baseUrl"
        type="url"
        required
        maxlength="2048"
        placeholder="https://api.example.com/v1"
        autocomplete="off"
      />

      <ModelEditor v-model:models="models" />
    </fieldset>

    <fieldset class="form__section">
      <legend>凭证</legend>
      <p class="form__hint">
        {{
          isEditing
            ? '密钥留空表示保持现有密钥，不会显示完整密钥。'
            : '可以暂不设置密钥，稍后再补充。'
        }}
      </p>

      <label for="profile-secret">API 密钥</label>
      <input
        id="profile-secret"
        v-model="secret"
        type="password"
        autocomplete="new-password"
        :disabled="clearSecret"
        :placeholder="isEditing ? '留空表示保持现有密钥' : '可选'"
      />

      <label v-if="hasStoredSecret" class="form__checkbox">
        <input v-model="clearSecret" type="checkbox" />
        清除已保存的密钥
      </label>
    </fieldset>

    <footer class="form__footer">
      <button type="submit" class="form__save" :disabled="busy">
        {{ busy ? '保存中…' : '保存档案' }}
      </button>
    </footer>
  </form>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  background: var(--color-surface);
}

.form__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.form__header h2 {
  margin: 0;
  font-size: var(--font-size-lg);
}

.form__section {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  align-items: center;
  gap: var(--space-2) var(--space-3);
  min-width: 0;
  margin: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}

.form__section legend {
  padding: 0 var(--space-1);
  font-weight: 600;
}

.form__section > input,
.form__section > select {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
  font: inherit;
}

.form__section > fieldset,
.form__hint,
.form__checkbox {
  grid-column: 1 / -1;
}

.form__hint {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.form__checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.form__error {
  margin: 0;
  color: var(--color-danger);
}

.form__footer {
  display: flex;
  justify-content: flex-end;
}

.form__save {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-4);
  background: var(--color-accent);
  color: #fff;
  font: inherit;
  cursor: pointer;
}

.form__save:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>