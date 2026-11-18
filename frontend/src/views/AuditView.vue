<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { listProfiles } from '../api/profiles'
import AuditEntryRow from '../components/AuditEntryRow.vue'
import AuditSnapshotDialog from '../components/AuditSnapshotDialog.vue'
import { useAuditStore } from '../stores/audit'
import { useToolsStore } from '../stores/tools'
import { groupAuditEntries } from '../utils/auditDisplay'

const audit = useAuditStore()
const toolsStore = useToolsStore()
const { entries, loading, loaded, error, activeToolId } = storeToRefs(audit)
const { tools } = storeToRefs(toolsStore)

const profileNames = ref<Record<string, string>>({})
const snapshotId = ref<string | null>(null)

const groups = computed(() => groupAuditEntries(entries.value))
const totalLabel = computed(() =>
  loaded.value ? '共 ' + entries.value.length + ' 条' : '读取中',
)
const selectedToolId = computed(() => activeToolId.value)

function toolName(toolId: string | null): string {
  if (toolId === null) {
    return '未知工具'
  }
  return tools.value.find((tool) => tool.id === toolId)?.display_name ?? toolId
}

async function loadProfiles(): Promise<void> {
  try {
    const response = await listProfiles()
    profileNames.value = Object.fromEntries(
      response.profiles.map((profile) => [profile.id, profile.name]),
    )
  } catch {
    profileNames.value = {}
  }
}

onMounted(() => {
  void Promise.all([toolsStore.fetchTools(), loadProfiles()])
  void audit.load(null)
})

function selectTool(toolId: string | null): void {
  void audit.load(toolId)
}

function openSnapshot(id: string): void {
  snapshotId.value = id
}
</script>

<template>
  <div class="audit-page">
    <header class="page-header">
      <div>
        <h1>操作记录</h1>
        <p>本机配置变更与快照，按时间倒序</p>
      </div>
      <span class="page-header__meta">{{ totalLabel }}</span>
    </header>

    <div class="audit-page__filter" aria-label="工具筛选">
      <span class="audit-page__filter-label">工具</span>
      <button
        class="audit-page__chip"
        :class="{ 'audit-page__chip--active': selectedToolId === null }"
        type="button"
        @click="selectTool(null)"
      >
        全部
      </button>
      <button
        v-for="tool in tools"
        :key="tool.id"
        class="audit-page__chip"
        :class="{ 'audit-page__chip--active': selectedToolId === tool.id }"
        type="button"
        :aria-label="'筛选 ' + tool.display_name"
        @click="selectTool(tool.id)"
      >
        {{ tool.display_name }}
      </button>
      <span class="audit-page__spacer"></span>
      <button class="button button--secondary audit-page__refresh" type="button" :disabled="loading" @click="selectTool(selectedToolId)">
        刷新
      </button>
    </div>

    <section class="audit-card" aria-label="操作记录列表">
      <div class="audit-card__head" aria-hidden="true">
        <span>时间</span><span>动作</span><span>工具 / 供应商</span><span>文件 / 字段</span><span>结果</span><span>说明</span><span>快照</span>
      </div>

      <div v-if="loading && !loaded" class="audit-card__state" role="status">正在读取操作记录…</div>
      <div v-else-if="error" class="audit-card__state audit-card__state--danger" role="alert">
        <strong>操作记录读取失败</strong>
        <span>{{ error }}</span>
        <button class="button button--secondary" type="button" @click="selectTool(selectedToolId)">重试</button>
      </div>
      <div v-else-if="entries.length === 0" class="audit-card__state">
        <strong>没有符合条件的操作记录</strong>
        <span>切换工具筛选，或完成一次配置操作后再回来查看。</span>
      </div>
      <template v-else>
        <div class="audit-card__body">
          <section v-for="group in groups" :key="group.key" class="audit-group" :aria-label="group.label">
          <div class="audit-group__title">
            <strong>{{ group.label }}</strong>
            <span>{{ group.entries.length }} 次操作</span>
          </div>
          <AuditEntryRow
            v-for="entry in group.entries"
            :key="entry.id"
            :entry="entry"
            :tool-name="toolName(entry.tool_id)"
            :profile-name="entry.profile_id ? profileNames[entry.profile_id] ?? entry.profile_id : null"
            @snapshot="openSnapshot"
          />
          </section>
        </div>
      </template>
      <footer class="audit-card__footer">
        <span>审计只保留可展示摘要，不包含密钥与文件原文。</span>
        <span>最多返回最近 200 条</span>
      </footer>
    </section>

    <AuditSnapshotDialog v-if="snapshotId" :snapshot-id="snapshotId" @close="snapshotId = null" />
  </div>
</template>

<style scoped>
.audit-page { display: flex; flex-direction: column; min-height: 0; height: 100%; background: var(--color-bg); }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-lg); min-height: 65px; padding: var(--space-md) var(--space-xl); border-bottom: 1px solid var(--color-border); background: var(--color-surface); }
.page-header h1 { margin: 0; font-size: var(--font-size-xl); line-height: var(--line-height-tight); }
.page-header p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.page-header__meta { color: var(--color-text-muted); font-size: var(--font-size-xs); }
.audit-page__filter { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-sm); margin: var(--space-xl) var(--space-xl) 0; padding: var(--space-sm) var(--space-md); border: 1px solid var(--color-border-card); border-radius: var(--radius-lg); background: var(--color-surface); }
.audit-page__filter-label { color: var(--color-text-secondary); font-size: var(--font-size-xs); font-weight: 600; }
.audit-page__chip { padding: 4px 9px; border: 1px solid transparent; border-radius: var(--radius-md); background: var(--color-bg-subtle); color: var(--color-info-fg); font-size: var(--font-size-xs); cursor: pointer; }
.audit-page__chip--active { border-color: var(--color-border-selected); background: var(--color-bg-selected); color: var(--color-primary-hover); font-weight: 600; }
.audit-page__spacer { flex: 1; }
.audit-page__refresh { min-height: 28px; font-size: var(--font-size-xs); }
.audit-card { display: flex; flex: 1; flex-direction: column; min-height: 0; margin: var(--space-md) var(--space-xl) var(--space-xl); border: 1px solid var(--color-border-card); border-radius: var(--radius-lg); background: var(--color-surface); overflow: hidden; }
.audit-card__head { display: grid; grid-template-columns: 78px 110px minmax(150px, 1fr) minmax(190px, 1.4fr) 62px minmax(170px, 1.1fr) 84px; gap: var(--space-md); padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--color-border); background: var(--color-bg); color: var(--color-text-secondary); font-size: 10px; font-weight: 600; }
.audit-card__state { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-sm); padding: var(--space-2xl); color: var(--color-text-secondary); font-size: var(--font-size-sm); text-align: center; }
.audit-card__state--danger { color: var(--color-danger-fg); }
.audit-card__state strong { color: var(--color-text); font-size: var(--font-size-md); }
.audit-card__state--danger strong { color: var(--color-danger-fg); }
.audit-card__body { flex: 1; min-height: 0; overflow-y: auto; }
.audit-group__title { display: flex; align-items: center; justify-content: space-between; gap: var(--space-md); padding: var(--space-sm) var(--space-lg); border-bottom: 1px solid var(--color-border); background: var(--color-surface); color: var(--color-info-fg); font-size: var(--font-size-xs); }
.audit-group__title span { color: var(--color-text-muted); }
.audit-card__footer { display: flex; justify-content: space-between; gap: var(--space-md); padding: var(--space-sm) var(--space-lg); border-top: 1px solid var(--color-border); color: var(--color-text-muted); font-size: 10px; }
@media (max-width: 1180px) {
  .audit-card__head { grid-template-columns: 70px 100px minmax(150px, 1fr) 62px minmax(160px, 1fr) 76px; }
  .audit-card__head span:nth-child(4) { display: none; }
}
@media (max-width: 760px) {
  .page-header { align-items: flex-start; }
  .audit-page__filter, .audit-card { margin-right: var(--space-lg); margin-left: var(--space-lg); }
  .audit-card__head { display: none; }
}
</style>
