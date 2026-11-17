<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { listProfiles } from '../api/profiles'
import type { ProfileListResponse, ProfileView } from '../api/profiles'
import type { ToolView } from '../api/tools'
import { useChatStore } from '../stores/chat'
import { useHistoryStore } from '../stores/history'
import { errorText } from '../utils/profileDisplay'
import { projectName } from '../utils/chatDisplay'
import ChatComposer from './ChatComposer.vue'
import HistoryPanel from './HistoryPanel.vue'
import HistoryTimeline from './HistoryTimeline.vue'
import ChatTranscript from './ChatTranscript.vue'
import ContextSwitcher from './ContextSwitcher.vue'
import ProjectDirPrompt from './ProjectDirPrompt.vue'
import ToolLogo from './ToolLogo.vue'
import ToolStatusBadge from './ToolStatusBadge.vue'

const props = defineProps<{ tool: ToolView }>()
const emit = defineEmits<{ 'show-detail': [] }>()

const chat = useChatStore()
const {
  sessions,
  current,
  currentLoading,
  currentError,
  sending,
  streaming,
  streamError,
} = storeToRefs(chat)

const history = useHistoryStore()
const {
  sessions: historySessions,
  loading: historyLoading,
  loaded: historyLoaded,
  error: historyError,
  warnings: historyWarnings,
  currentId: historyCurrentId,
  messages: historyMessages,
  detailLoading: historyDetailLoading,
  detailError: historyDetailError,
  detailWarnings: historyDetailWarnings,
  messagesHasMore: historyHasMore,
  totalMessages: historyTotal,
} = storeToRefs(history)

const mode = ref<'chat' | 'history'>('chat')
const historyTitle = computed(
  () => historySessions.value.find((item) => item.id === historyCurrentId.value)?.title ?? null,
)

const profilesData = ref<ProfileListResponse | null>(null)
const profilesError = ref<string | null>(null)
const actionError = ref<string | null>(null)
const creating = ref(false)
const dirPromptOpen = ref(false)

const canChat = computed(() => props.tool.capabilities.sessions === true)
const activeBinding = computed(
  () =>
    profilesData.value?.bindings.find(
      (binding) => binding.tool_id === props.tool.id && binding.active,
    ) ?? null,
)
const activeProfile = computed<ProfileView | null>(() => {
  const binding = activeBinding.value
  if (binding === null || profilesData.value === null) {
    return null
  }
  return profilesData.value.profiles.find((profile) => profile.id === binding.profile_id) ?? null
})
const sessionProfile = computed<ProfileView | null>(() => {
  const session = current.value
  if (session === null || profilesData.value === null) {
    return null
  }
  return profilesData.value.profiles.find((profile) => profile.id === session.profile_id) ?? null
})
const modelOptions = computed(() => sessionProfile.value?.models ?? [])
const effortLevels = computed(() =>
  props.tool.capabilities.reasoning_effort === true
    ? props.tool.capabilities.reasoning_effort_levels ?? []
    : [],
)
const projectLabel = computed(() =>
  current.value === null ? '—' : projectName(current.value.project_dir),
)
const sessionTitle = computed(() => current.value?.title ?? '新会话')

async function loadProfiles(): Promise<void> {
  profilesError.value = null
  try {
    const data = await listProfiles(props.tool.id)
    profilesData.value = {
      profiles: Array.isArray(data.profiles) ? data.profiles : [],
      bindings: Array.isArray(data.bindings) ? data.bindings : [],
      secret_store: data.secret_store,
      warnings: Array.isArray(data.warnings) ? data.warnings : [],
    }
  } catch (caught) {
    profilesError.value = errorText(caught, '供应商读取失败')
  }
}

async function chooseSession(): Promise<void> {
  if (current.value !== null && current.value.tool_id === props.tool.id) {
    return
  }
  const match = sessions.value.find((session) => session.tool_id === props.tool.id)
  if (match === undefined) {
    chat.clearCurrent()
    return
  }
  await chat.openSession(match.id)
}

async function initialize(): Promise<void> {
  await Promise.all([chat.fetchSessions(), loadProfiles()])
  await chooseSession()
}

onMounted(() => {
  void initialize()
})

watch(
  () => props.tool.id,
  () => {
    chat.clearCurrent()
    history.reset()
    mode.value = 'chat'
    profilesData.value = null
    actionError.value = null
    void initialize()
  },
)

async function openHistory(): Promise<void> {
  mode.value = 'history'
  await history.fetchSessions(props.tool.id)
  if (historySessions.value.length > 0 && historyCurrentId.value === null) {
    await history.openSession(historySessions.value[0]?.id ?? '')
  }
}

function handleHistorySelect(sessionId: string): void {
  void history.openSession(sessionId)
}

function handleLoadEarlier(): void {
  void history.loadEarlier()
}

function handleHistoryRetry(): void {
  void openHistory()
}

async function createSession(projectDir: string): Promise<void> {
  const profile = activeProfile.value
  if (profile === null) {
    actionError.value = '这个工具还没有启用供应商，请先到供应商页启用一个。'
    return
  }
  creating.value = true
  actionError.value = null
  try {
    const created = await chat.createSession({
      tool_id: props.tool.id,
      profile_id: profile.id,
      project_dir: projectDir,
    })
    if (created === null) {
      actionError.value = currentError.value ?? '创建会话失败'
      return
    }
    dirPromptOpen.value = false
  } finally {
    creating.value = false
  }
}

function handleNew(): void {
  if (!canChat.value || creating.value) {
    return
  }
  actionError.value = null
  const remembered = chat.lastProjectFor(props.tool.id)
  if (remembered === null) {
    dirPromptOpen.value = true
    return
  }
  void createSession(remembered)
}

async function handleModel(value: string | null): Promise<void> {
  actionError.value = null
  try {
    await chat.updateCurrent({ model: value })
  } catch (caught) {
    actionError.value = errorText(caught, '切换模型失败')
  }
}

async function handleEffort(value: string | null): Promise<void> {
  actionError.value = null
  try {
    await chat.updateCurrent({ reasoning_effort: value })
  } catch (caught) {
    actionError.value = errorText(caught, '切换思考强度失败')
  }
}

async function handleSend(content: string): Promise<void> {
  await chat.send(content)
}

async function handleStop(): Promise<void> {
  await chat.stop()
}
</script>

<template>
  <section class="chat" aria-labelledby="chat-title">
    <header class="chat__header">
      <div class="chat__heading">
        <ToolLogo :tool-id="tool.id" size="md" />
        <h1 id="chat-title" class="chat__title">{{ tool.display_name }}</h1>
        <ToolStatusBadge :status="tool.status" />
        <span v-if="current !== null" class="chat__session-title">{{ sessionTitle }}</span>
      </div>
      <div class="chat__actions">
        <div class="chat__modes" role="group" aria-label="工作台视图">
          <button
            class="chat__mode"
            :class="{ 'chat__mode--active': mode === 'chat' }"
            type="button"
            @click="mode = 'chat'"
          >
            对话
          </button>
          <button
            class="chat__mode"
            :class="{ 'chat__mode--active': mode === 'history' }"
            type="button"
            @click="openHistory"
          >
            历史
          </button>
        </div>
        <button class="chat__link" type="button" @click="emit('show-detail')">详情</button>
        <button
          v-if="mode === 'chat'"
          class="icon-button"
          type="button"
          aria-label="新建会话"
          :disabled="!canChat || creating"
          @click="handleNew"
        >
          +
        </button>
      </div>
    </header>

    <div v-if="mode === 'chat' && current !== null && canChat" class="chat__context">
      <span class="chat__project" :title="current.project_dir">{{ projectLabel }}</span>
      <ContextSwitcher
        :model="current.model"
        :models="modelOptions"
        :effort="current.reasoning_effort"
        :effort-levels="effortLevels"
        :disabled="sending"
        @update:model="handleModel"
        @update:effort="handleEffort"
      />
      <span class="chat__spacer"></span>
      <span class="chat__status">{{ current.status === 'running' ? '执行中' : '空闲' }}</span>
    </div>

    <div v-if="profilesError !== null" class="chat__banner" role="alert">{{ profilesError }}</div>
    <div v-if="actionError !== null" class="chat__banner" role="alert">{{ actionError }}</div>

    <div v-if="mode === 'history'" class="chat__history">
      <HistoryPanel
        :sessions="historySessions"
        :selected-id="historyCurrentId"
        :loading="historyLoading"
        :loaded="historyLoaded"
        :error="historyError"
        :warnings="historyWarnings"
        @select="handleHistorySelect"
        @retry="handleHistoryRetry"
      />
      <HistoryTimeline
        :title="historyTitle"
        :session-id="historyCurrentId"
        :messages="historyMessages"
        :loading="historyDetailLoading"
        :error="historyDetailError"
        :warnings="historyDetailWarnings"
        :has-more="historyHasMore"
        :total-messages="historyTotal"
        @load-earlier="handleLoadEarlier"
      />
    </div>

    <div v-else-if="!canChat" class="chat__fallback">
      <h2>这个工具不支持应用内对话</h2>
      <p>可以查看工具配置，或切换到支持对话的工具；这里不会显示一个输入后无效的输入框。</p>
      <button class="button button--secondary" type="button" @click="emit('show-detail')">
        查看详情
      </button>
    </div>

    <div v-else-if="current === null" class="chat__fallback">
      <h2>{{ currentLoading ? '正在读取会话…' : '这个工具还没有会话' }}</h2>
      <p v-if="!currentLoading">点击右上角「+」直接开始；项目目录会沿用该工具最近一次会话。</p>
      <p v-if="currentError !== null" class="chat__fallback-error" role="alert">{{ currentError }}</p>
      <button v-if="!currentLoading" class="button" type="button" :disabled="creating" @click="handleNew">
        新建会话
      </button>
    </div>

    <template v-else>
      <ChatTranscript :messages="current.messages" :streaming="streaming" />
      <div v-if="streamError !== null" class="chat__banner chat__banner--inline" role="alert">
        {{ streamError }}
      </div>
      <ChatComposer
        :disabled="current === null"
        :sending="sending"
        placeholder="描述任务，Enter 发送 / Shift+Enter 换行"
        hint="会话使用本地工具执行，不经过云端"
        @send="handleSend"
        @stop="handleStop"
      />
    </template>

    <ProjectDirPrompt
      v-if="dirPromptOpen"
      :busy="creating"
      :error="actionError"
      @confirm="createSession"
      @cancel="dirPromptOpen = false"
    />
  </section>
</template>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  background: var(--color-bg);
}

.chat__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-lg);
  min-height: 65px;
  padding: var(--space-md) var(--space-xl);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.chat__heading {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-width: 0;
}

.chat__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 700;
  line-height: var(--line-height-tight);
}

.chat__session-title {
  padding-left: var(--space-sm);
  border-left: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--space-sm);
}

.chat__modes {
  display: inline-flex;
  padding: 2px;
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.chat__mode {
  padding: 5px 10px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
}

.chat__mode--active {
  background: var(--color-surface);
  color: var(--color-primary-hover);
  font-weight: 600;
}

.chat__history {
  display: grid;
  flex: 1;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: 0;
}

.chat__link {
  padding: 4px 6px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 600;
  cursor: pointer;
}

.chat__link:hover {
  background: var(--color-bg-subtle);
}

.chat__context {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-xl);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.chat__project {
  max-width: 220px;
  padding: 5px 10px;
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__spacer {
  flex: 1;
}

.chat__status {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.chat__banner {
  margin: var(--space-sm) var(--space-xl) 0;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.chat__banner--inline {
  margin: 0 var(--space-xl) var(--space-sm);
}

.chat__fallback {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-2xl);
  text-align: center;
}

.chat__fallback h2 {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.chat__fallback p {
  max-width: 460px;
  margin: 0 0 var(--space-sm);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

.chat__fallback-error {
  color: var(--color-danger-fg);
}
</style>



