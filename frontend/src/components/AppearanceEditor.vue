<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import type { AppearanceOverride, BubblePreset } from '../api/appearances'
import type { ToolView } from '../api/tools'
import { useAppearancesStore } from '../stores/appearances'
import { appearanceStyle, resolveAppearance } from '../utils/appearances'

const props = defineProps<{
  tool: ToolView
  override: AppearanceOverride | undefined
}>()

const store = useAppearancesStore()
const editing = ref(false)
const defaults = computed(() => resolveAppearance(props.tool))
const draft = reactive({
  accent_color: defaults.value.accentLight,
  background_color: defaults.value.chatBackgroundLight,
  bubble_preset: defaults.value.bubblePreset as BubblePreset,
})
const previewStyle = computed(() => appearanceStyle(resolveAppearance(props.tool, props.override)))

function resetDraft(): void {
  const resolved = resolveAppearance(props.tool, props.override)
  draft.accent_color = resolved.accentLight
  draft.background_color = resolved.chatBackgroundLight
  draft.bubble_preset = resolved.bubblePreset
}

watch(
  () => [props.tool.id, props.override] as const,
  () => {
    editing.value = false
    store.clearOperationError()
    resetDraft()
  },
)

async function save(): Promise<void> {
  const saved = await store.save(props.tool.id, { ...draft })
  if (saved) {
    editing.value = false
  }
}

async function restoreDefault(): Promise<void> {
  if (!window.confirm(`恢复 ${props.tool.display_name} 的默认外观？`)) {
    return
  }
  if (await store.reset(props.tool.id)) {
    editing.value = false
    resetDraft()
  }
}

function cancel(): void {
  editing.value = false
  store.clearOperationError()
  resetDraft()
}
</script>

<template>
  <section class="appearance-editor" :style="previewStyle" aria-labelledby="appearance-heading">
    <header class="appearance-editor__header">
      <div>
        <h3 id="appearance-heading" class="appearance-editor__title">好友外观</h3>
        <p class="appearance-editor__description">
          默认样式稳定跟随工具身份；覆盖只保存在本机，不随档案切换。
        </p>
      </div>
      <div class="appearance-editor__actions">
        <button
          v-if="!editing"
          type="button"
          class="appearance-editor__button"
          @click="editing = true; resetDraft(); store.clearOperationError()"
        >
          编辑外观
        </button>
        <button
          type="button"
          class="appearance-editor__button appearance-editor__button--secondary"
          @click="restoreDefault"
        >
          恢复默认
        </button>
      </div>
    </header>

    <p v-if="store.loadError !== null" class="appearance-editor__error" role="alert">
      外观覆盖读取失败：{{ store.loadError }}
    </p>
    <p v-if="store.operationError !== null" class="appearance-editor__error" role="alert">
      外观保存 / 恢复失败：{{ store.operationError }}
    </p>

    <form v-if="editing" class="appearance-editor__form" @submit.prevent="save">
      <label class="appearance-editor__field">
        <span>强调色</span>
        <input v-model="draft.accent_color" type="color" aria-label="强调色" />
      </label>
      <label class="appearance-editor__field">
        <span>聊天背景色</span>
        <input v-model="draft.background_color" type="color" aria-label="聊天背景色" />
      </label>
      <label class="appearance-editor__field appearance-editor__field--preset">
        <span>气泡样式</span>
        <select v-model="draft.bubble_preset" aria-label="气泡样式">
          <option value="soft">柔和</option>
          <option value="rounded">圆角</option>
          <option value="compact">紧凑</option>
        </select>
      </label>
      <div class="appearance-editor__actions appearance-editor__actions--form">
        <button type="submit" class="appearance-editor__button" :disabled="store.loading">
          保存
        </button>
        <button
          type="button"
          class="appearance-editor__button appearance-editor__button--secondary"
          @click="cancel"
        >
          取消
        </button>
      </div>
    </form>

    <div v-else class="appearance-editor__preview" aria-label="当前外观预览">
      <span class="appearance-editor__swatch" aria-hidden="true"></span>
      <span>强调色 / 聊天背景 / {{ override?.bubble_preset ?? defaults.bubblePreset }}</span>
    </div>
  </section>
</template>

<style scoped>
.appearance-editor {
  --friend-accent: var(--friend-accent-light);
  --friend-avatar-fg-light: var(--friend-avatar-foreground-light);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  color: var(--color-text);
}

.appearance-editor__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.appearance-editor__title {
  margin: 0;
  font-size: var(--font-size-md);
}

.appearance-editor__description {
  margin: var(--space-1) 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.appearance-editor__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.appearance-editor__button {
  min-height: 2.25rem;
  border: 1px solid var(--friend-accent);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  background: var(--friend-accent);
  color: var(--friend-avatar-fg-light, #ffffff);
  font: inherit;
  cursor: pointer;
}

.appearance-editor__button--secondary {
  background: var(--color-surface);
  color: var(--friend-accent);
}

.appearance-editor__button:focus-visible,
.appearance-editor__field input:focus-visible,
.appearance-editor__field select:focus-visible {
  outline: 2px solid var(--friend-accent);
  outline-offset: 2px;
}

.appearance-editor__button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.appearance-editor__error {
  margin: var(--space-3) 0 0;
  color: var(--color-danger);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.appearance-editor__form {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.appearance-editor__field {
  display: flex;
  flex: 1 1 8rem;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.appearance-editor__field input,
.appearance-editor__field select {
  width: 100%;
  min-height: 2.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text);
}

.appearance-editor__field input[type='color'] {
  padding: 0.2rem;
}

.appearance-editor__actions--form {
  align-self: end;
}

.appearance-editor__preview {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.appearance-editor__swatch {
  width: 1.25rem;
  height: 1.25rem;
  flex: 0 0 auto;
  border: 2px solid var(--friend-accent);
  border-radius: 50%;
  background: var(--friend-chat-background-light);
}

@media (prefers-color-scheme: dark) {
  .appearance-editor {
    --friend-accent: var(--friend-accent-dark);
    --friend-avatar-fg-dark: var(--friend-avatar-foreground-dark);
  }

  .appearance-editor__button {
    color: var(--friend-avatar-fg-dark, #ffffff);
  }

  .appearance-editor__button--secondary {
    color: var(--friend-accent);
  }

  .appearance-editor__swatch {
    background: var(--friend-chat-background-dark);
  }
}
</style>
