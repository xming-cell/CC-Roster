<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import AppearanceEditor from '../components/AppearanceEditor.vue'
import type { ToolStatus } from '../api/tools'
import type { SwitchApplyResponse } from '../api/switch'
import DetailSkeleton from '../components/DetailSkeleton.vue'
import EmptyTools from '../components/EmptyTools.vue'
import FriendList from '../components/FriendList.vue'
import GlobalWarnings from '../components/GlobalWarnings.vue'
import SnapshotPanel from '../components/SnapshotPanel.vue'
import SwitchPanel from '../components/SwitchPanel.vue'
import ToolDetailPanel from '../components/ToolDetailPanel.vue'
import ToolStatusBadge from '../components/ToolStatusBadge.vue'
import { useProfilesStore } from '../stores/profiles'
import { useAppearancesStore } from '../stores/appearances'
import { useSnapshotsStore } from '../stores/snapshots'
import { useToolsStore } from '../stores/tools'
import { appearanceStyle, resolveAppearance } from '../utils/appearances'
import { normalizeStatus } from '../utils/tools'

const store = useToolsStore()
const profilesStore = useProfilesStore()
const appearancesStore = useAppearancesStore()
const snapshotsStore = useSnapshotsStore()
const {
  profiles,
  bindings,
  error: profilesError,
} = storeToRefs(profilesStore)
const {
  sortedTools,
  warnings,
  loading,
  error,
  refreshError,
  selectedToolId,
  selectedTool,
  detailLoading,
  detailError,
} = storeToRefs(store)
const { appearances } = storeToRefs(appearancesStore)

const searchQuery = ref('')
const statusFilter = ref<ToolStatus | 'all'>('all')
const debouncedQuery = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

const filteredTools = computed(() => {
  const input = debouncedQuery.value.trim().toLowerCase()
  let result = sortedTools.value

  if (input !== '') {
    result = result.filter((tool) => {
      const haystack = [tool.display_name, tool.provider ?? '', tool.model ?? ''].join(' ').toLowerCase()
      return haystack.includes(input)
    })
  }

  if (statusFilter.value !== 'all') {
    result = result.filter((tool) => tool.status === statusFilter.value)
  }

  return result
})

const initialLoading = computed(
  () => loading.value && sortedTools.value.length === 0 && error.value === null,
)

const selectedSummary = computed(() => {
  if (selectedToolId.value === null) {
    return null
  }
  return sortedTools.value.find((tool) => tool.id === selectedToolId.value) ?? null
})

const headerTool = computed(() => selectedTool.value ?? selectedSummary.value)
const headerStatus = computed(() =>
  headerTool.value === null ? null : normalizeStatus(headerTool.value.status),
)
const headerAppearanceStyle = computed(() =>
  headerTool.value === null
    ? {}
    : appearanceStyle(
        resolveAppearance(headerTool.value, appearances.value[headerTool.value.id]),
      ),
)

function applySearch(value: string): void {
  if (searchTimer !== null) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    debouncedQuery.value = value
  }, 200)
}

function clearFilters(): void {
  searchQuery.value = ''
  debouncedQuery.value = ''
  statusFilter.value = 'all'
}

watch(
  () => searchQuery.value,
  (value) => {
    applySearch(value)
  },
)

function selectTool(toolId: string): void {
  void store.selectTool(toolId)
}

async function handleApplied(result: SwitchApplyResponse): Promise<void> {
  await Promise.all([store.fetchTools(), profilesStore.fetchProfiles()])
  if (store.selectedToolId === result.tool_id) {
    await store.selectTool(result.tool_id)
  }
  await snapshotsStore.fetchSnapshots(result.tool_id)
}

onMounted(() => {
  void Promise.all([
    store.fetchTools(),
    profilesStore.fetchProfiles(),
    appearancesStore.fetchAppearances(),
  ])
})
</script>

<template>
  <div class="home">
    <aside class="home__sidebar" aria-label="AI 好友">
      <header class="home__sidebar-header">
        <h1 class="home__title">AI 伙伴</h1>
        <button
          type="button"
          class="home__refresh"
          :disabled="loading"
          @click="store.fetchTools()"
        >
          刷新
        </button>
      </header>

      <GlobalWarnings v-if="warnings.length > 0" :warnings="warnings" />

      <p v-if="refreshError !== null" class="home__refresh-error" role="status">
        刷新失败，当前显示上次结果：{{ refreshError }}
      </p>

      <div class="home__toolbar" role="search">
        <label class="home__search">
          <span class="sr-only">搜索工具</span>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索名称 / 供应商 / 模型"
            aria-label="搜索工具"
          />
        </label>
        <div class="home__status-filters" aria-label="状态筛选">
          <button
            v-for="option in ['all', 'ok', 'unconfigured', 'error']"
            :key="option"
            type="button"
            class="home__status-button"
            :class="{ 'home__status-button--active': statusFilter === option }"
            :aria-pressed="statusFilter === option"
            @click="statusFilter = option as ToolStatus | 'all'"
          >
            {{ option === 'all' ? '全部' : option === 'ok' ? '正常' : option === 'unconfigured' ? '未配置' : '异常' }}
          </button>
        </div>
      </div>

      <div
        v-if="filteredTools.length === 0 && !loading && sortedTools.length > 0"
        class="home__empty-state"
        role="status"
      >
        <p class="home__empty-title">没有匹配项</p>
        <p class="home__empty-text">尝试更换关键词或调整状态筛选。</p>
        <button type="button" class="home__clear-filters" @click="clearFilters()">清除筛选</button>
      </div>

      <FriendList
        v-else
        :tools="filteredTools"
        :loading="loading"
        :error="error"
        :selected-id="selectedToolId"
        @select="selectTool"
        @retry="store.fetchTools()"
      />
    </aside>

    <section class="home__detail" :style="headerAppearanceStyle" aria-label="详情与会话">
      <DetailSkeleton v-if="initialLoading" />
      <p v-else-if="error !== null" class="home__placeholder">
        工具列表加载失败，请重试
      </p>
      <EmptyTools v-else-if="sortedTools.length === 0" />
      <template v-else-if="headerTool !== null">
        <header class="home__detail-header">
          <h2 class="home__detail-name">{{ headerTool.display_name }}</h2>
          <ToolStatusBadge v-if="headerStatus !== null" :status="headerStatus" />
        </header>

        <div class="home__detail-body">
          <ToolDetailPanel
            :tool="selectedTool"
            :loading="detailLoading"
            :error="detailError"
            embedded
          />
          <p v-if="profilesError !== null" class="home__profiles-error">
            档案列表读取失败：{{ profilesError }}
          </p>
          <SwitchPanel
            :tool="headerTool"
            :profiles="profiles"
            :bindings="bindings"
            @applied="handleApplied"
          />
          <SnapshotPanel :tool-id="headerTool.id" />
          <AppearanceEditor
            :tool="headerTool"
            :override="appearances[headerTool.id]"
          />
          <!-- 012 / 014 的会话时间线容器；本卡不渲染会话内容 -->
          <section class="home__timeline" aria-label="会话时间线"></section>
        </div>
      </template>

      <p v-else class="home__placeholder">选择一个 AI 查看详情</p>
    </section>
  </div>
</template>

<style scoped>
.home {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  background: var(--color-surface);
}

.home__sidebar {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  width: var(--sidebar-width);
  min-height: 0;
  border-right: 1px solid var(--color-border);
  background: var(--color-sidebar-bg);
}

.home__toolbar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.home__search {
  display: block;
}

.home__search input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  color: var(--color-text);
  font: inherit;
}

.home__search input:focus-visible {
  outline: 2px solid var(--friend-accent);
  outline-offset: 2px;
}

.home__status-filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.home__status-button {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  padding: 0.125rem var(--space-2);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font: inherit;
  cursor: pointer;
}

.home__status-button--active {
  border-color: var(--friend-accent);
  background: var(--friend-accent-soft);
  color: var(--friend-accent);
}

.home__status-button:focus-visible {
  outline: 2px solid var(--friend-accent);
  outline-offset: 2px;
}

.home__empty-state {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  color: var(--color-text-secondary);
}

.home__empty-title {
  margin: 0;
  color: var(--color-text);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.home__empty-text {
  margin: 0;
}

.home__clear-filters {
  align-self: flex-start;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.home__sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.home__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.home__refresh {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}

.home__refresh:hover:not(:disabled) {
  color: var(--friend-accent);
  border-color: var(--friend-accent);
}

.home__refresh:focus-visible {
  outline: 2px solid var(--friend-accent);
  outline-offset: 2px;
}

.home__refresh:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.home__refresh-error {
  margin: 0;
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  background: var(--status-error-bg);
  color: var(--status-error-fg);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.home__detail {
  --friend-accent: var(--friend-accent-light);
  --friend-chat-background: var(--friend-chat-background-light);
  --friend-chat-foreground: var(--friend-chat-foreground-light);
  --friend-secondary: var(--friend-secondary-light);
  --bubble-radius: var(--friend-bubble-radius);
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.home__detail-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  box-shadow: inset 3px 0 0 var(--friend-secondary);
}

.home__detail-name {
  overflow: hidden;
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home__detail-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-4);
}

.home__timeline {
  flex: 1;
  min-height: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--bubble-radius, var(--radius-md));
  background: var(--friend-chat-background);
  color: var(--friend-chat-foreground);
}

.home__profiles-error {
  margin: 0;
  color: var(--color-danger);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.home__placeholder {
  display: grid;
  flex: 1;
  place-items: center;
  margin: 0;
  color: var(--color-text-secondary);
}

@media (max-width: 767px) {
  .home {
    flex-direction: column;
  }

  .home__sidebar {
    width: 100%;
    max-height: 40vh;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .home__detail {
    flex: 1;
  }
}

@media (prefers-color-scheme: dark) {
  .home__detail {
    --friend-accent: var(--friend-accent-dark);
    --friend-chat-background: var(--friend-chat-background-dark);
    --friend-chat-foreground: var(--friend-chat-foreground-dark);
    --friend-secondary: var(--friend-secondary-dark);
  }
}
</style>