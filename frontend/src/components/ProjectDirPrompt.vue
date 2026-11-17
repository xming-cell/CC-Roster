<script setup lang="ts">
import { computed, ref } from 'vue'

import { ApiError } from '../api/client'
import { pickDirectory } from '../api/system'
import { errorText } from '../utils/profileDisplay'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  busy: boolean
  error: string | null
}>()

const emit = defineEmits<{
  confirm: [path: string]
  cancel: []
}>()

const value = ref('')
const browseBusy = ref(false)
const browseError = ref<string | null>(null)
const browseAvailable = ref(isLocalPage())
const shownError = computed(() => props.error ?? browseError.value)

function isLocalPage(): boolean {
  if (typeof window === 'undefined') {
    return true
  }
  const host = window.location.hostname
  return host === '' || host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]'
}

async function browse(): Promise<void> {
  if (browseBusy.value || props.busy || !browseAvailable.value) {
    return
  }
  browseBusy.value = true
  browseError.value = null
  try {
    const result = await pickDirectory()
    if (!result.cancelled && result.path !== null && result.path.trim().length > 0) {
      value.value = result.path
    }
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 501) {
      browseAvailable.value = false
      browseError.value = '系统目录选择不可用，请手动输入绝对路径。'
    } else {
      browseError.value = errorText(caught, '打开系统目录选择器失败，请手动输入路径。')
    }
  } finally {
    browseBusy.value = false
  }
}

function submit(): void {
  const path = value.value.trim()
  if (path.length === 0 || browseBusy.value) {
    return
  }
  emit('confirm', path)
}
</script>

<template>
  <ModalShell labelled-by="project-dir-title" @close="emit('cancel')">
    <div class="dir">
      <h2 id="project-dir-title" class="dir__title">选择项目目录</h2>
      <p class="dir__text">
        这个工具还没有历史会话。输入一次绝对路径后，后续新会话会自动沿用。
      </p>
      <label class="dir__label" for="project-dir-input">项目目录（绝对路径）</label>
      <div class="dir__path-row">
        <input
          id="project-dir-input"
          v-model="value"
          class="dir__input"
          type="text"
          placeholder="D:\\projects\\demo"
          @keydown.enter.prevent="submit"
        />
        <button
          v-if="browseAvailable"
          class="button button--secondary dir__browse"
          type="button"
          :disabled="busy || browseBusy"
          aria-label="浏览项目目录"
          @click="browse"
        >
          {{ browseBusy ? '打开中…' : '浏览…' }}
        </button>
      </div>
      <p class="dir__hint">浏览会打开系统文件夹选择器；取消不会修改当前输入。</p>
      <p v-if="shownError !== null" class="dir__error" role="alert">{{ shownError }}</p>
      <footer class="dir__footer">
        <button class="button button--secondary" type="button" :disabled="busy" @click="emit('cancel')">
          取消
        </button>
        <button class="button" type="button" :disabled="busy || browseBusy || value.trim().length === 0" @click="submit">
          {{ busy ? '创建中…' : '创建会话' }}
        </button>
      </footer>
    </div>
  </ModalShell>
</template>

<style scoped>
.dir {
  padding: var(--space-xl);
}

.dir__title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
}

.dir__text {
  margin: var(--space-sm) 0 var(--space-lg);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

.dir__label {
  display: block;
  margin-bottom: var(--space-xs);
  color: var(--color-info-fg);
  font-size: var(--font-size-xs);
}

.dir__input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-md);
  font: inherit;
  font-size: var(--font-size-sm);
}

.dir__error {
  margin: var(--space-sm) 0 0;
  color: var(--color-danger-fg);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.dir__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  margin-top: var(--space-xl);
}

.dir__path-row {
  display: flex;
  gap: var(--space-sm);
}

.dir__path-row .dir__input {
  flex: 1;
  min-width: 0;
}

.dir__browse {
  flex: none;
  min-height: 40px;
}

.dir__hint {
  margin: var(--space-sm) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}
</style>
