<script setup lang="ts">
import { computed, ref } from 'vue'

import { ApiError } from '../api/client'
import {
  importLocalProfiles,
  importProfiles,
  previewLocalConfigImport,
  previewProfileImport,
} from '../api/profileImport'
import type {
  ImportItemStatus,
  ImportPolicy,
  ProfileImportPreview,
  ProfileImportResult,
} from '../api/profileImport'
import type { ToolView } from '../api/tools'
import { errorText } from '../utils/profileDisplay'
import ModalShell from './ModalShell.vue'

type Stage = 'select' | 'parsing' | 'preview' | 'importing' | 'error'
type SourceMode = 'file' | 'local'

const LOCAL_TOOL_IDS = ['claude-code', 'codex-cli', 'gemini-cli', 'opencode'] as const

const props = defineProps<{
  tools: ToolView[]
  currentToolId: string
}>()

const emit = defineEmits<{
  close: []
  imported: [result: ProfileImportResult, toolId: string | null]
}>()

const stage = ref<Stage>('select')
const sourceMode = ref<SourceMode>('file')
const selectedLocalTool = ref<string | null>(null)
const content = ref('')
const fileName = ref('')
const preview = ref<ProfileImportPreview | null>(null)
const policy = ref<ImportPolicy>('skip')
const error = ref<string | null>(null)
const errorCode = ref<string | null>(null)
const dragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const localRows = computed(() =>
  LOCAL_TOOL_IDS.map((id) => {
    const tool = props.tools.find((candidate) => candidate.id === id)
    return {
      id,
      name: tool?.display_name ?? id,
      path: tool?.config_path ?? '未发现配置文件',
      available: tool !== undefined && tool.last_modified !== null,
    }
  }),
)
const selectedLocalName = computed(
  () => localRows.value.find((row) => row.id === selectedLocalTool.value)?.name ?? '本机配置',
)

const busy = computed(() => stage.value === 'parsing' || stage.value === 'importing')
const canConfirm = computed(
  () => stage.value === 'preview' && preview.value?.can_import === true && !busy.value,
)
const title = computed(() => {
  if (stage.value === 'error') {
    return '无法读取导入来源'
  }
  if (stage.value === 'preview' || stage.value === 'importing') {
    if (preview.value?.source === 'local_config') {
      return '预览本机配置'
    }
    return preview.value?.source === 'codex_config' ? '预览 Codex 配置' : '预览导入'
  }
  return '导入供应商'
})
const subtitle = computed(() => {
  if (sourceMode.value === 'local') {
    return '从本机配置读取；不读取 OAuth / 环境变量，不修改原文件'
  }
  return fileName.value === '' ? '从本地 JSON / TOML 文件导入，不会自动绑定或启用' : fileName.value
})
const errorHint = computed(() => {
  if (errorCode.value?.startsWith('LOCAL_') === true) {
    return '检查工具配置文件是否存在、可读且结构正确。'
  }
  if (errorCode.value?.startsWith('CODEX_') === true) {
    return '检查 CODEX_HOME 或 ~/.codex/config.toml 是否存在、可读，并包含 model_providers。'
  }
  return '检查文件是否带 schema_version = 1，且 profiles 是数组；JSON 与 TOML 都支持。'
})
const previewSourceLabel = computed(() => {
  if (preview.value?.source === 'local_config') {
    return selectedLocalName.value + ' 配置'
  }
  if (preview.value?.source === 'codex_config') {
    return 'Codex 配置'
  }
  return preview.value?.format === 'toml' ? '本地 TOML 文件' : '本地 JSON 文件'
})

const statusLabels: Record<ImportItemStatus, string> = {
  new: '新增',
  duplicate: '重复',
  invalid: '非法',
}

function switchSource(mode: SourceMode): void {
  if (busy.value || sourceMode.value === mode) {
    return
  }
  sourceMode.value = mode
  if (mode === 'local') {
    selectedLocalTool.value =
      localRows.value.find((row) => row.available)?.id ?? localRows.value[0]?.id ?? null
  }
  content.value = ''
  fileName.value = ''
  preview.value = null
  error.value = null
  errorCode.value = null
  stage.value = 'select'
}

function openPicker(): void {
  if (!busy.value) {
    fileInput.value?.click()
  }
}

async function acceptFiles(files: FileList | null | undefined): Promise<void> {
  const file = files?.[0]
  if (file === undefined) {
    return
  }
  const lower = file.name.toLowerCase()
  if (!lower.endsWith('.json') && !lower.endsWith('.toml')) {
    stage.value = 'error'
    error.value = '请选择 .json 或 .toml 文件'
    errorCode.value = 'IMPORT_INVALID_FILE'
    return
  }
  sourceMode.value = 'file'
  fileName.value = file.name
  let text: string
  try {
    text = await file.text()
  } catch {
    stage.value = 'error'
    error.value = '读取文件失败，请确认文件仍可访问'
    errorCode.value = 'IMPORT_READ_FAILED'
    return
  }
  content.value = text
  await loadPreview()
}

async function loadPreview(): Promise<void> {
  if (content.value.length === 0) {
    return
  }
  stage.value = 'parsing'
  error.value = null
  errorCode.value = null
  try {
    preview.value = await previewProfileImport(content.value, props.currentToolId)
    stage.value = 'preview'
  } catch (caught) {
    preview.value = null
    error.value = errorText(caught, '解析导入文件失败')
    errorCode.value = caught instanceof ApiError ? caught.code : null
    stage.value = 'error'
  }
}

async function readLocalConfig(): Promise<void> {
  if (busy.value || selectedLocalTool.value === null) {
    return
  }
  sourceMode.value = 'local'
  stage.value = 'parsing'
  error.value = null
  errorCode.value = null
  try {
    preview.value = await previewLocalConfigImport(selectedLocalTool.value)
    stage.value = 'preview'
  } catch (caught) {
    preview.value = null
    error.value = errorText(caught, '读取本机配置失败')
    errorCode.value = caught instanceof ApiError ? caught.code : null
    stage.value = 'error'
  }
}

async function confirm(): Promise<void> {
  if (!canConfirm.value || preview.value === null) {
    return
  }
  stage.value = 'importing'
  error.value = null
  try {
    let result: ProfileImportResult
    let importedToolId: string | null
    if (preview.value.source === 'local_config') {
      if (selectedLocalTool.value === null) {
        stage.value = 'preview'
        return
      }
      result = await importLocalProfiles(selectedLocalTool.value, policy.value)
      importedToolId = selectedLocalTool.value
    } else {
      importedToolId = props.currentToolId === '' ? null : props.currentToolId
      result = await importProfiles(content.value, policy.value, importedToolId ?? undefined)
    }
    emit('imported', result, importedToolId)
    emit('close')
  } catch (caught) {
    error.value = errorText(caught, '导入失败，请稍后重试')
    errorCode.value = caught instanceof ApiError ? caught.code : null
    stage.value = 'preview'
  }
}

function retrySource(): void {
  if (sourceMode.value === 'local') {
    void readLocalConfig()
  } else {
    openPicker()
  }
}

function handleDrop(event: DragEvent): void {
  dragging.value = false
  if (sourceMode.value === 'file') {
    void acceptFiles(event.dataTransfer?.files)
  }
}

function close(): void {
  if (!busy.value) {
    emit('close')
  }
}
</script>

<template>
  <ModalShell labelled-by="import-title" size="wide" @close="close">
    <div class="import">
      <header class="import__header">
        <div class="import__heading">
          <h2 id="import-title" class="import__title">{{ title }}</h2>
          <p class="import__subtitle">{{ subtitle }}</p>
        </div>
        <button class="import__close" type="button" aria-label="关闭" :disabled="busy" @click="close">
          ✕
        </button>
      </header>

      <template v-if="stage === 'select' || stage === 'parsing'">
        <div class="import__sources" aria-label="导入来源">
          <button
            class="import__source-card"
            :class="{ 'import__source-card--active': sourceMode === 'file' }"
            type="button"
            :disabled="busy"
            @click="switchSource('file')"
          >
            <span class="import__source-icon" aria-hidden="true">↑</span>
            <span><strong>本地文件</strong><small>JSON / TOML · 最大 1 MB</small></span>
          </button>
          <button
            class="import__source-card"
            :class="{ 'import__source-card--active': sourceMode === 'local' }"
            type="button"
            :disabled="busy"
            @click="switchSource('local')"
          >
            <span class="import__source-icon import__source-icon--codex" aria-hidden="true">&gt;_</span>
            <span><strong>从本机配置读取</strong><small>Claude / Codex / Gemini / OpenCode</small></span>
          </button>
        </div>

        <template v-if="sourceMode === 'file'">
          <button
            class="import__dropzone"
            :class="{ 'import__dropzone--drag': dragging }"
            type="button"
            :disabled="busy"
            @click="openPicker"
            @dragenter.prevent="dragging = true"
            @dragover.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop.prevent="handleDrop"
          >
            <span class="import__dropzone-icon" aria-hidden="true">↑</span>
            <strong>{{ stage === 'parsing' ? '正在解析文件…' : '选择文件，或把 JSON / TOML 拖到这里' }}</strong>
            <span class="import__dropzone-hint">.json / .toml · schema_version = 1 · 最大 1 MB</span>
          </button>
          <input
            ref="fileInput"
            class="sr-only"
            type="file"
            accept=".json,.toml,application/json,application/toml"
            aria-label="选择导入文件"
            @change="acceptFiles(($event.target as HTMLInputElement).files)"
          />
        </template>

        <div v-else class="import__local-source">
          <div class="import__local-list" role="radiogroup" aria-label="本机配置来源">
            <button
              v-for="row in localRows"
              :key="row.id"
              class="import__local-row"
              :class="{ 'import__local-row--active': selectedLocalTool === row.id }"
              type="button"
              :disabled="busy || !row.available"
              @click="selectedLocalTool = row.id"
            >
              <span class="import__local-name">{{ row.name }}</span>
              <span class="import__local-path">{{ row.path }}</span>
              <span class="import__local-status">
                {{ row.available ? (selectedLocalTool === row.id ? '已选择' : '可读取') : '未发现配置' }}
              </span>
            </button>
          </div>
          <div class="import__local-actions">
            <p>只读取配置文件，不读取 OAuth / 环境变量；导入后绑定到来源工具，保持未启用。</p>
          </div>
        </div>

        <ul class="import__hints">
          <li>导入前先预览新增、重复与非法条目。</li>
          <li>重复项默认跳过，可改为覆盖。</li>
          <li>本机配置里的密钥只进本机密钥库，预览只显示「有密钥 / 无密钥」。</li>
          <li>导入后绑定到来源工具，不自动启用；存在非法条目时整批取消。</li>
        </ul>
      </template>

      <template v-else-if="stage === 'error'">
        <div class="import__alert import__alert--danger" role="alert">
          <div class="import__alert-head">
            <strong>{{ error }}</strong>
            <span class="import__badge import__badge--danger">未写入</span>
          </div>
          <p v-if="errorCode !== null" class="import__code">code: {{ errorCode }}</p>
          <p class="import__alert-hint">{{ errorHint }}</p>
        </div>
      </template>

      <template v-else-if="preview !== null">
        <div class="import__source-strip">
          <div>
            <span>来源</span>
            <strong>{{ previewSourceLabel }}</strong>
          </div>
          <code v-if="preview.source_path !== null">{{ preview.source_path }}</code>
          <span class="import__format">{{ preview.format.toUpperCase() }}</span>
        </div>

        <div class="import__totals">
          <div class="import__total import__total--new"><span>新增</span><strong>{{ preview.totals.new }}</strong></div>
          <div class="import__total import__total--duplicate"><span>重复</span><strong>{{ preview.totals.duplicate }}</strong></div>
          <div class="import__total import__total--invalid"><span>非法</span><strong>{{ preview.totals.invalid }}</strong></div>
        </div>

        <ul class="import__items" aria-label="导入条目">
          <li v-for="entry in preview.items" :key="entry.index" class="import__item">
            <span class="import__badge" :class="'import__badge--' + entry.status">
              {{ statusLabels[entry.status] }}
            </span>
            <div class="import__item-main">
              <div class="import__item-title">
                <strong class="import__item-name">{{ entry.name ?? '（未命名条目）' }}</strong>
                <span class="import__secret" :class="{ 'import__secret--missing': !entry.has_secret }">
                  {{ entry.has_secret ? '有密钥' : '无密钥' }}
                </span>
              </div>
              <span v-for="reason in entry.reasons" :key="reason" class="import__item-reason">{{ reason }}</span>
              <span v-for="note in entry.notes" :key="note" class="import__item-note">{{ note }}</span>
              <span v-if="entry.reasons.length === 0 && entry.notes.length === 0" class="import__item-reason">可以导入</span>
            </div>
          </li>
        </ul>

        <div class="import__policy" role="radiogroup" aria-label="重复项处理">
          <span class="import__policy-label">重复项处理</span>
          <label class="import__policy-option" :class="{ 'import__policy-option--active': policy === 'skip' }">
            <input v-model="policy" type="radio" value="skip" />
            跳过
          </label>
          <label class="import__policy-option" :class="{ 'import__policy-option--active': policy === 'overwrite' }">
            <input v-model="policy" type="radio" value="overwrite" />
            覆盖
          </label>
          <span class="import__policy-hint">默认跳过；覆盖会更新已有供应商的模型与密钥</span>
        </div>

        <p v-if="!preview.can_import" class="import__invalid-hint" role="alert">
          存在 {{ preview.totals.invalid }} 条非法项，确认导入不可用；修正来源后重新读取。
        </p>
        <p v-else-if="error" class="import__alert" role="alert">{{ error }}</p>
      </template>

      <footer class="import__footer">
        <span class="import__footer-hint">确认前不会写入任何供应商。</span>
        <div class="import__actions">
          <template v-if="stage === 'error'">
            <button class="button button--secondary" type="button" @click="close">取消</button>
            <button class="button" type="button" @click="retrySource">
              {{ sourceMode === 'local' ? '重新读取' : '重新选择' }}
            </button>
          </template>
          <template v-else-if="stage === 'preview'">
            <button class="button button--secondary" type="button" @click="close">取消</button>
            <button class="button" type="button" :disabled="!canConfirm" @click="confirm">
              {{ error === null ? '确认导入' : '重试导入' }}
            </button>
          </template>
          <template v-else>
            <button class="button button--secondary" type="button" :disabled="busy" @click="close">取消</button>
            <button v-if="sourceMode === 'file'" class="button" type="button" :disabled="busy" @click="openPicker">
              {{ stage === 'parsing' ? '解析中…' : '选择文件' }}
            </button>
            <button v-else class="button" type="button" :disabled="busy || selectedLocalTool === null" @click="readLocalConfig">
              {{ stage === 'parsing' ? '读取中…' : '读取所选配置' }}
            </button>
          </template>
        </div>
      </footer>
    </div>
  </ModalShell>
</template>

<style scoped>
.import {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  padding: var(--space-xl);
}

.import__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-lg);
}

.import__heading {
  min-width: 0;
}

.import__title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: var(--line-height-tight);
}

.import__subtitle {
  margin: 2px 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.import__close {
  flex: none;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.import__close:hover:not(:disabled) {
  background: var(--color-bg-subtle);
  color: var(--color-text);
}

.import__dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xl);
  border: 1px dashed var(--color-border-control);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  color: var(--color-text);
  cursor: pointer;
}

.import__dropzone:hover:not(:disabled),
.import__dropzone--drag {
  border-color: var(--color-primary);
  background: var(--color-bg-selected);
}

.import__dropzone-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--color-bg-selected);
  color: var(--color-primary);
  font-size: var(--font-size-lg);
  font-weight: 700;
}

.import__dropzone strong {
  font-size: var(--font-size-md);
}

.import__dropzone-hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.import__hints {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  margin: 0;
  padding-left: 18px;
  color: var(--color-info-fg);
  font-size: var(--font-size-xs);
}

.import__totals {
  display: flex;
  gap: var(--space-sm);
}

.import__total {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-md);
  border-radius: var(--radius-lg);
}

.import__total span {
  font-size: var(--font-size-xs);
}

.import__total strong {
  font-size: var(--font-size-lg);
}

.import__total--new {
  background: var(--color-success-bg);
  color: var(--color-success-fg);
}

.import__total--duplicate {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.import__total--invalid {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.import__items {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  margin: 0;
  padding: 0;
  list-style: none;
}

.import__item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-md);
}

.import__item-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.import__item-name {
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.import__item-reason {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.import__badge {
  flex: none;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.import__badge--new {
  background: var(--color-success-bg);
  color: var(--color-success-fg);
}

.import__badge--duplicate {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.import__badge--invalid,
.import__badge--danger {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.import__policy {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm);
}

.import__policy-label {
  color: var(--color-info-fg);
  font-size: var(--font-size-xs);
}

.import__policy-option {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: 6px 12px;
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  font-size: var(--font-size-xs);
  cursor: pointer;
}

.import__policy-option--active {
  border-color: var(--color-border-selected);
  background: var(--color-bg-selected);
  color: var(--color-primary-hover);
  font-weight: 600;
}

.import__policy-option input {
  margin: 0;
}

.import__policy-hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.import__invalid-hint {
  margin: 0;
  color: var(--color-danger-fg);
  font-size: var(--font-size-xs);
}

.import__alert {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-lg);
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.import__alert p {
  margin: 0;
}

.import__alert--danger {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.import__alert-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.import__alert-hint {
  font-size: var(--font-size-xs);
}

.import__code {
  color: inherit;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  opacity: 0.85;
}

.import__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-lg);
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border);
}

.import__footer-hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.import__actions {
  display: flex;
  flex: none;
  gap: var(--space-sm);
}

.import__sources {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-sm);
}

.import__source-card {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
}

.import__source-card--active {
  border-color: var(--color-border-selected);
  background: var(--color-bg-selected);
}

.import__source-card span:last-child {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.import__source-card strong {
  font-size: var(--font-size-sm);
}

.import__source-card small {
  color: var(--color-text-secondary);
  font-size: 10px;
}

.import__source-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: var(--radius-md);
  background: var(--color-bg-selected);
  color: var(--color-primary);
  font-size: var(--font-size-md);
  font-weight: 700;
}

.import__source-icon--codex {
  font-family: var(--font-mono);
  font-size: 11px;
}

.import__local-source {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.import__local-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.import__local-row {
  display: grid;
  grid-template-columns: minmax(96px, auto) minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-sm);
  padding: 10px 12px;
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
}

.import__local-row--active {
  border-color: var(--color-border-selected);
  background: var(--color-bg-selected);
}

.import__local-row:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.import__local-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.import__local-path {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import__local-status {
  color: var(--color-text-muted);
  font-size: 10px;
}

.import__local-row--active .import__local-status {
  color: var(--color-primary);
  font-weight: 600;
}

.import__local-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.import__local-actions p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-relaxed);
}

.import__codex-source {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-lg);
  padding: var(--space-lg);
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
}

.import__codex-main {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
  min-width: 0;
}

.import__codex-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex: none;
  border-radius: var(--radius-md);
  background: var(--color-bg-selected);
  color: var(--color-primary);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
}

.import__codex-main strong {
  font-size: var(--font-size-sm);
}

.import__codex-main p {
  margin: 2px 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-relaxed);
}

.import__codex-main code {
  font-family: var(--font-mono);
  font-size: 10px;
}

.import__source-strip {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--font-size-xs);
}

.import__source-strip > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.import__source-strip span {
  color: var(--color-text-muted);
  font-size: 9px;
}

.import__source-strip strong {
  color: var(--color-info-fg);
  font-size: var(--font-size-xs);
}

.import__source-strip code {
  flex: 1;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
  overflow-wrap: anywhere;
}

.import__format {
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--color-bg-subtle);
  color: var(--color-info-fg) !important;
  font-size: 9px !important;
  font-weight: 600;
}

.import__item-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm);
}

.import__secret {
  padding: 2px 6px;
  border-radius: 999px;
  background: var(--color-success-bg);
  color: var(--color-success-fg);
  font-size: 9px;
  font-weight: 600;
}

.import__secret--missing {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.import__item-note {
  color: var(--color-warning-fg);
  font-size: var(--font-size-xs);
}

@media (max-width: 620px) {
  .import__sources {
    grid-template-columns: 1fr;
  }

  .import__local-source {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.import__local-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.import__local-row {
  display: grid;
  grid-template-columns: minmax(96px, auto) minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-sm);
  padding: 10px 12px;
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
}

.import__local-row--active {
  border-color: var(--color-border-selected);
  background: var(--color-bg-selected);
}

.import__local-row:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.import__local-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.import__local-path {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import__local-status {
  color: var(--color-text-muted);
  font-size: 10px;
}

.import__local-row--active .import__local-status {
  color: var(--color-primary);
  font-weight: 600;
}

.import__local-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.import__local-actions p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-relaxed);
}

.import__codex-source {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
