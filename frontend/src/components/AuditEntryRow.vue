<script setup lang="ts">
import { computed } from 'vue'

import type { AuditEntry } from '../api/audit'
import {
  auditActionLabel,
  auditResultLabel,
  auditResultTone,
  fileBasename,
  formatAuditTime,
} from '../utils/auditDisplay'
import ToolLogo from './ToolLogo.vue'

const props = defineProps<{
  entry: AuditEntry
  toolName: string
  profileName: string | null
}>()

const emit = defineEmits<{ snapshot: [snapshotId: string] }>()
const tone = computed(() => auditResultTone(props.entry.result))
</script>

<template>
  <article class="audit-row" :aria-label="auditActionLabel(entry.action) + ' ' + auditResultLabel(entry.result)">
    <time class="audit-row__time" :datetime="entry.created_at">
      <strong>{{ formatAuditTime(entry.created_at) }}</strong>
      <span>{{ entry.result === 'success' ? '完成' : '需关注' }}</span>
    </time>

    <span class="audit-row__action">{{ auditActionLabel(entry.action) }}</span>

    <div class="audit-row__target">
      <div class="audit-row__tool">
        <ToolLogo :tool-id="entry.tool_id ?? 'unknown'" size="sm" />
        <strong>{{ toolName }}</strong>
      </div>
      <span>{{ profileName ?? entry.profile_id ?? '未关联供应商' }}</span>
    </div>

    <div class="audit-row__changes">
      <div v-if="entry.files.length > 0" class="audit-row__chips">
        <span v-for="file in entry.files.slice(0, 2)" :key="file" class="audit-row__chip audit-row__chip--mono">
          {{ fileBasename(file) }}
        </span>
        <span v-if="entry.files.length > 2" class="audit-row__chip">+{{ entry.files.length - 2 }}</span>
      </div>
      <span v-else class="audit-row__muted">没有文件变化</span>
      <span class="audit-row__fields">
        {{ entry.fields.length === 0 ? '没有字段变化' : entry.fields.join(' · ') }}
      </span>
    </div>

    <span class="audit-row__result" :class="'audit-row__result--' + tone">
      {{ auditResultLabel(entry.result) }}
    </span>

    <p class="audit-row__message">{{ entry.message }}</p>

    <div class="audit-row__snapshot">
      <button
        v-if="entry.snapshot_id"
        class="audit-row__link"
        type="button"
        :aria-label="'查看快照 ' + entry.snapshot_id"
        @click="emit('snapshot', entry.snapshot_id)"
      >
        查看快照
      </button>
      <span v-else class="audit-row__muted">不可用</span>
    </div>
  </article>
</template>

<style scoped>
.audit-row {
  display: grid;
  grid-template-columns: 78px 110px minmax(150px, 1fr) minmax(190px, 1.4fr) 62px minmax(170px, 1.1fr) 84px;
  gap: var(--space-md);
  align-items: center;
  min-height: 72px;
  padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--color-bg-subtle);
}

.audit-row__time {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--color-text);
}

.audit-row__time strong {
  font-size: var(--font-size-md);
}

.audit-row__time span,
.audit-row__target span,
.audit-row__fields,
.audit-row__muted {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.audit-row__action {
  justify-self: start;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-subtle);
  color: var(--color-info-fg);
  font-size: var(--font-size-xs);
  font-weight: 600;
  white-space: nowrap;
}

.audit-row__target,
.audit-row__changes,
.audit-row__message {
  min-width: 0;
}

.audit-row__tool {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 3px;
}

.audit-row__tool strong {
  overflow: hidden;
  font-size: var(--font-size-md);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-row__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
}

.audit-row__chip {
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-subtle);
  color: var(--color-info-fg);
  font-size: 10px;
}

.audit-row__chip--mono {
  font-family: var(--font-mono);
}

.audit-row__fields {
  display: block;
  margin-top: 3px;
  overflow-wrap: anywhere;
}

.audit-row__result {
  justify-self: start;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.audit-row__result--success {
  background: var(--color-success-bg);
  color: var(--color-success-fg);
}

.audit-row__result--warning {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.audit-row__result--danger {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.audit-row__message {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-relaxed);
  overflow-wrap: anywhere;
}

.audit-row__link {
  padding: 2px 4px;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 600;
  cursor: pointer;
}

.audit-row__link:hover {
  text-decoration: underline;
}

@media (max-width: 1180px) {
  .audit-row {
    grid-template-columns: 70px 100px minmax(150px, 1fr) 62px minmax(160px, 1fr) 76px;
  }

  .audit-row__changes {
    grid-column: 3 / 5;
  }

  .audit-row__message {
    grid-column: 5 / 7;
  }
}

@media (max-width: 760px) {
  .audit-row {
    grid-template-columns: 1fr 1fr;
  }

  .audit-row__changes,
  .audit-row__message {
    grid-column: 1 / -1;
  }
}
</style>
