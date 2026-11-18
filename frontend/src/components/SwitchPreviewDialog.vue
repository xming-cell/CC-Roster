<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'

import type { ProfileView } from '../api/profiles'
import type { ToolView } from '../api/tools'
import { useSwitchStore } from '../stores/switch'
import { formatDateTime } from '../utils/profileDisplay'
import { fileBasename, shortHash } from '../utils/switchDisplay'
import ModalShell from './ModalShell.vue'
import SwitchDiffTable from './SwitchDiffTable.vue'

const props = defineProps<{
  tool: ToolView
  profile: ProfileView
}>()

const emit = defineEmits<{
  close: []
  changed: []
}>()

const store = useSwitchStore()
const { stage, preview, result, error, rollbackStage, rollbackResult, rollbackError, busy } =
  storeToRefs(store)

onMounted(() => {
  void store.start(props.tool, props.profile)
})

watch(stage, (value) => {
  if (value === 'applied') {
    emit('changed')
  }
})

watch(rollbackStage, (value) => {
  if (value === 'done') {
    emit('changed')
  }
})

const title = computed(() => {
  if (stage.value === 'applied') {
    return '切换完成'
  }
  if (stage.value === 'conflict') {
    return '无法应用切换'
  }
  return '切换供应商'
})

const subtitle = computed(() => `${props.tool.display_name} · 将启用 ${props.profile.name}`)
const canApply = computed(
  () => stage.value === 'ready' && preview.value?.can_apply === true && !busy.value,
)
const applying = computed(() => stage.value === 'applying')
const rolling = computed(() => rollbackStage.value === 'rolling')
const rollbackConfirming = computed(
  () => rollbackStage.value === 'confirm' || rollbackStage.value === 'rolling',
)
const rolledBack = computed(() => rollbackStage.value === 'done')
const restartMessage = computed(() => preview.value?.restart_message ?? '')

function close(): void {
  if (busy.value) {
    return
  }
  store.close()
  emit('close')
}
</script>

<template>
  <ModalShell labelled-by="switch-title" size="wide" @close="close">
    <div class="switch">
      <header class="switch__header">
        <div class="switch__heading">
          <h2 id="switch-title" class="switch__title">{{ title }}</h2>
          <p class="switch__subtitle">{{ subtitle }}</p>
        </div>
        <button class="switch__close" type="button" aria-label="关闭" :disabled="busy" @click="close">
          ✕
        </button>
      </header>

      <div v-if="stage === 'previewing'" class="switch__loading" role="status">
        <strong>正在生成预览…</strong>
        <span>只读取目标文件，不会写入任何内容。</span>
      </div>

      <div v-else-if="stage === 'error'" class="switch__alert" role="alert">
        <strong>预览失败</strong>
        <p>{{ error }}</p>
      </div>

      <div v-else-if="stage === 'conflict'" class="switch__alert switch__alert--danger" role="alert">
        <div class="switch__alert-head">
          <strong>预览已失效</strong>
          <span class="switch__badge switch__badge--danger">未写入</span>
        </div>
        <p>{{ error }}</p>
        <p class="switch__alert-hint">为避免覆盖你的改动，本次没有写入任何文件。</p>
      </div>

      <template v-else-if="stage === 'applied' && result !== null">
        <div class="switch__success">
          <span class="switch__success-icon" aria-hidden="true">✓</span>
          <div>
            <strong class="switch__success-title">已应用 {{ result.files.length }} 个文件</strong>
            <p class="switch__success-text">{{ formatDateTime(result.applied_at) }}</p>
          </div>
        </div>

        <section class="switch__snapshot" aria-label="快照">
          <div class="switch__snapshot-main">
            <span class="switch__label">快照</span>
            <code class="switch__code">{{ result.snapshot_id }}</code>
            <span class="switch__meta">{{ result.files.length }} 个文件 · 可逐字节回滚</span>
          </div>
          <button
            v-if="rollbackStage === 'idle'"
            class="button button--secondary"
            type="button"
            @click="store.requestRollback()"
          >
            回滚到快照
          </button>
        </section>

        <ul class="switch__files" aria-label="已写入文件">
          <li v-for="file in result.files" :key="file.path" class="switch__file">
            <span class="switch__file-name" :title="file.path">{{ fileBasename(file.path) }}</span>
            <span class="switch__badge switch__badge--success">已更新</span>
            <span class="switch__file-hash">{{ shortHash(file.sha256) }}</span>
          </li>
        </ul>

        <p v-if="result.restart_required" class="switch__restart">
          <strong>重启后生效</strong>
          <span>{{ result.restart_message }}</span>
        </p>

        <p class="switch__audit">审计记录已生成：<code class="switch__code">{{ result.audit_id }}</code></p>

        <div v-if="rollbackConfirming" class="switch__rollback" role="alertdialog" aria-label="确认回滚">
          <strong>回滚到这次切换之前？</strong>
          <p>会恢复快照中的 {{ result.files.length }} 个文件；回滚本身也会生成一份可再恢复的快照。</p>
          <p v-if="rollbackError" class="switch__rollback-error" role="alert">{{ rollbackError }}</p>
          <div class="switch__rollback-actions">
            <button class="button button--secondary" type="button" :disabled="rolling" @click="store.cancelRollback()">
              取消回滚
            </button>
            <button class="button" type="button" :disabled="rolling" @click="store.confirmRollback()">
              {{ rolling ? '回滚中…' : '确认回滚' }}
            </button>
          </div>
        </div>

        <p v-if="rolledBack" class="switch__rolled" role="status">
          已回滚到 {{ rollbackResult?.snapshot_id }}。回滚前的状态保存在
          {{ rollbackResult?.pre_rollback_snapshot_id }}。
        </p>
      </template>

      <template v-else-if="preview !== null">
        <div class="switch__summary">
          <div class="switch__summary-item">
            <span class="switch__label">工具</span>
            <strong>{{ tool.display_name }}</strong>
          </div>
          <span class="switch__arrow" aria-hidden="true">→</span>
          <div class="switch__summary-item switch__summary-item--target">
            <span class="switch__label">供应商</span>
            <strong>{{ profile.name }}</strong>
          </div>
        </div>

        <h3 class="switch__section-title">字段变更</h3>
        <SwitchDiffTable :files="preview.files" />

        <div v-if="preview.blockers.length > 0" class="switch__alert switch__alert--danger" role="alert">
          <div class="switch__alert-head">
            <strong>存在阻止应用的项</strong>
            <span class="switch__badge switch__badge--danger">{{ preview.blockers.length }} 项</span>
          </div>
          <ul class="switch__list">
            <li v-for="blocker in preview.blockers" :key="blocker.code + blocker.message">
              {{ blocker.message }}
              <span v-if="blocker.path !== null" class="switch__path">（{{ blocker.path }}）</span>
            </li>
          </ul>
        </div>

        <div v-if="preview.warnings.length > 0" class="switch__alert switch__alert--warning" role="status">
          <strong>需要注意</strong>
          <ul class="switch__list">
            <li v-for="warning in preview.warnings" :key="warning.code + warning.message">
              {{ warning.message }}
            </li>
          </ul>
        </div>

        <p v-if="preview.restart_required" class="switch__restart">
          <strong>重启后生效</strong>
          <span>{{ restartMessage }}</span>
        </p>

        <p v-if="error" class="switch__alert" role="alert">{{ error }}</p>
      </template>

      <footer class="switch__footer">
        <span class="switch__hint">
          {{ stage === 'applied' ? '回滚会先保存当前状态。' : '预览为只读，取消后磁盘不会发生任何变化。' }}
        </span>
        <div class="switch__actions">
          <template v-if="stage === 'applied'">
            <button class="button" type="button" :disabled="rollbackConfirming" @click="close">完成</button>
          </template>
          <template v-else-if="stage === 'conflict'">
            <button class="button button--secondary" type="button" @click="close">取消</button>
            <button class="button" type="button" :disabled="busy" @click="store.retryPreview()">重新检查</button>
          </template>
          <template v-else-if="stage === 'error'">
            <button class="button button--secondary" type="button" @click="close">取消</button>
            <button class="button" type="button" :disabled="busy" @click="store.retryPreview()">重新检查</button>
          </template>
          <template v-else>
            <button class="button button--secondary" type="button" :disabled="busy" @click="close">取消</button>
            <button class="button" type="button" :disabled="!canApply" @click="store.apply()">
              {{ applying ? '应用中…' : '应用切换' }}
            </button>
          </template>
        </div>
      </footer>
    </div>
  </ModalShell>
</template>

<style scoped>
.switch {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  padding: var(--space-xl);
}

.switch__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-lg);
}

.switch__heading {
  min-width: 0;
}

.switch__title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: var(--line-height-tight);
}

.switch__subtitle {
  margin: 2px 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.switch__close {
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

.switch__close:hover:not(:disabled) {
  background: var(--color-bg-subtle);
  color: var(--color-text);
}

.switch__loading {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  padding: var(--space-xl);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  font-size: var(--font-size-sm);
}

.switch__loading span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.switch__summary {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.switch__summary-item {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: var(--space-md);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  overflow-wrap: anywhere;
}

.switch__summary-item--target {
  background: var(--color-bg-selected);
}

.switch__label {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.switch__arrow {
  flex: none;
  color: var(--color-text-muted);
}

.switch__section-title {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-info-fg);
}

.switch__alert {
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

.switch__alert p {
  margin: 0;
  line-height: var(--line-height-relaxed);
}

.switch__alert--danger {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.switch__alert--warning {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.switch__alert-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.switch__alert-hint {
  font-size: var(--font-size-xs);
}

.switch__list {
  margin: 0;
  padding-left: 18px;
}

.switch__path {
  color: inherit;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  opacity: 0.85;
}

.switch__badge {
  flex: none;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.switch__badge--danger {
  background: color-mix(in srgb, var(--color-danger) 14%, transparent);
  color: var(--color-danger-fg);
}

.switch__badge--success {
  background: var(--color-success-bg);
  color: var(--color-success-fg);
}

.switch__restart {
  display: flex;
  gap: var(--space-sm);
  margin: 0;
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-lg);
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
  font-size: var(--font-size-xs);
}

.switch__success {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.switch__success-icon {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--color-success-bg);
  color: var(--color-success);
  font-size: var(--font-size-lg);
  font-weight: 700;
}

.switch__success-title {
  font-size: var(--font-size-lg);
}

.switch__success-text {
  margin: 2px 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.switch__snapshot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-lg);
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
}

.switch__snapshot-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.switch__code {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.switch__meta {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.switch__files {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  margin: 0;
  padding: 0;
  list-style: none;
}

.switch__file {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.switch__file-name {
  flex: 1;
  font-weight: 600;
}

.switch__file-hash {
  flex: none;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.switch__audit {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.switch__rollback {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-lg);
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  font-size: var(--font-size-sm);
}

.switch__rollback p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-relaxed);
}

.switch__rollback-error {
  color: var(--color-danger-fg);
}

.switch__rollback-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
}

.switch__rolled {
  margin: 0;
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-lg);
  background: var(--color-success-bg);
  color: var(--color-success-fg);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.switch__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-lg);
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border);
}

.switch__hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.switch__actions {
  display: flex;
  flex: none;
  gap: var(--space-sm);
}
</style>
