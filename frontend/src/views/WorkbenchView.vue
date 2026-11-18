<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import ChatWorkspace from '../components/ChatWorkspace.vue'
import SessionList from '../components/SessionList.vue'
import ToolDetailPanel from '../components/ToolDetailPanel.vue'
import ToolListPanel from '../components/ToolListPanel.vue'
import { useChatStore } from '../stores/chat'
import { useToolsStore } from '../stores/tools'

const store = useToolsStore()
const chat = useChatStore()
const {
  tools,
  warnings,
  loading,
  loaded,
  error,
  selectedToolId,
  selectedTool,
  detailLoading,
  detailError,
} = storeToRefs(store)
const { sessions, sessionsLoading, sessionsLoaded, sessionsError, current } = storeToRefs(chat)

const detailOpen = ref(false)

onMounted(() => {
  void store.fetchTools()
  void chat.fetchSessions()
})

watch(
  () => selectedToolId.value,
  () => {
    detailOpen.value = false
  },
)

const showChat = computed(
  () =>
    selectedTool.value !== null &&
    selectedTool.value.capabilities.sessions === true &&
    !detailOpen.value,
)

function handleRefresh(): void {
  void store.fetchTools()
}

function handleSelect(toolId: string): void {
  void store.selectTool(toolId)
}

function handleRetryDetail(): void {
  if (store.selectedToolId !== null) {
    void store.selectTool(store.selectedToolId)
  }
}

async function handleSession(sessionId: string): Promise<void> {
  const session = sessions.value.find((item) => item.id === sessionId)
  await chat.openSession(sessionId)
  if (session !== undefined && session.tool_id !== selectedToolId.value) {
    void store.selectTool(session.tool_id)
  }
}

function handleSessionRetry(): void {
  void chat.fetchSessions()
}
</script>

<template>
  <div class="workbench">
    <h1 class="sr-only">工作台</h1>

    <div class="workbench__side">
      <div class="workbench__tools">
        <ToolListPanel
          :tools="tools"
          :warnings="warnings"
          :loading="loading"
          :loaded="loaded"
          :error="error"
          :selected-tool-id="selectedToolId"
          @refresh="handleRefresh"
          @select="handleSelect"
        />
      </div>
      <SessionList
        :sessions="sessions"
        :selected-id="current?.id ?? null"
        :loading="sessionsLoading"
        :loaded="sessionsLoaded"
        :error="sessionsError"
        @select="handleSession"
        @retry="handleSessionRetry"
      />
    </div>

    <main class="workbench__main">
      <template v-if="showChat && selectedTool !== null">
        <ChatWorkspace :tool="selectedTool" @show-detail="detailOpen = true" />
      </template>
      <template v-else>
        <div v-if="detailOpen && selectedTool !== null" class="workbench__bar">
          <button class="workbench__back" type="button" @click="detailOpen = false">
            ← 返回对话
          </button>
        </div>
        <ToolDetailPanel
          :tool="selectedTool"
          :loading="detailLoading"
          :error="detailError"
          :selected-tool-id="selectedToolId"
          @retry="handleRetryDetail"
        />
      </template>
    </main>
  </div>
</template>

<style scoped>
.workbench {
  display: grid;
  grid-template-columns: var(--layout-list-width) minmax(0, 1fr);
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.workbench__side {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--color-border);
}

.workbench__tools {
  display: flex;
  flex: 0 1 auto;
  max-height: 55%;
  min-height: 0;
}

.workbench__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.workbench__bar {
  display: flex;
  align-items: center;
  padding: var(--space-sm) var(--space-xl);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.workbench__back {
  padding: 4px 8px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 600;
  cursor: pointer;
}

.workbench__back:hover {
  background: var(--color-bg-subtle);
}

@media (max-width: 980px) {
  .workbench {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 42vh) minmax(0, 1fr);
  }
}
</style>

