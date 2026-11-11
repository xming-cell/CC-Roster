<script setup lang="ts">
import { computed, ref } from 'vue'

import type { BindingView, ProfileView } from '../api/profiles'
import type { ToolView } from '../api/tools'

const props = defineProps<{
  tools: ToolView[]
  profiles: ProfileView[]
  bindings: BindingView[]
  toolsError: string | null
  busyToolId: string | null
  error: string | null
}>()

const emit = defineEmits<{
  bind: [toolId: string, profileId: string]
  unbind: [toolId: string]
}>()

const selection = ref<Record<string, string>>({})

const orphanBindings = computed(() =>
  props.bindings.filter(
    (binding) => !props.tools.some((tool) => tool.id === binding.tool_id),
  ),
)

function bindingFor(toolId: string): BindingView | undefined {
  return props.bindings.find((binding) => binding.tool_id === toolId)
}

function profileName(profileId: string): string {
  return (
    props.profiles.find((profile) => profile.id === profileId)?.name ?? profileId
  )
}

function submitBind(toolId: string): void {
  const profileId = selection.value[toolId]
  if (profileId !== undefined && profileId !== '') {
    emit('bind', toolId, profileId)
  }
}

function appliedAtFor(toolId: string): string | null {
  return bindingFor(toolId)?.applied_at ?? null
}

function snapshotIdFor(toolId: string): string | null {
  return bindingFor(toolId)?.snapshot_id ?? null
}

function needsReapply(toolId: string): boolean {
  const binding = bindingFor(toolId)
  if (binding === undefined || binding.applied_at === null) {
    return false
  }
  const profile = props.profiles.find((entry) => entry.id === binding.profile_id)
  if (profile === undefined) {
    return false
  }
  const applied = new Date(binding.applied_at).getTime()
  const updated = new Date(profile.updated_at).getTime()
  if (Number.isNaN(applied) || Number.isNaN(updated)) {
    return false
  }
  return updated > applied
}

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('zh-CN', { hour12: false })
}
</script>

<template>
  <section class="bindings" aria-label="工具绑定">
    <header class="bindings__header">
      <h2>工具绑定</h2>
      <p class="bindings__hint">
        绑定只记录工具当前选择的档案，不会立即修改配置；在主界面详情中预览并应用后才会写入。
      </p>
    </header>

    <p v-if="toolsError !== null" class="bindings__error" role="alert">
      工具列表读取失败：{{ toolsError }}
    </p>
    <p v-if="error !== null" class="bindings__error" role="alert">{{ error }}</p>
    <p v-if="profiles.length === 0" class="bindings__empty">
      暂无可绑定档案，请先新建档案。
    </p>

    <ul v-if="tools.length > 0" class="bindings__list">
      <li v-for="tool in tools" :key="tool.id" class="bindings__row">
        <div class="bindings__tool">
          <strong>{{ tool.display_name }}</strong>
          <span v-if="bindingFor(tool.id)" class="bindings__current">
            当前档案：{{ profileName(bindingFor(tool.id)?.profile_id ?? '') }}
          </span>
        </div>

        <div class="bindings__controls">
          <label :for="`binding-${tool.id}`">为 {{ tool.display_name }} 选择档案</label>
          <select
            :id="`binding-${tool.id}`"
            v-model="selection[tool.id]"
            :disabled="busyToolId !== null || profiles.length === 0"
          >
            <option value="">选择档案</option>
            <option v-for="profile in profiles" :key="profile.id" :value="profile.id">
              {{ profile.name }}
            </option>
          </select>
          <button
            type="button"
            :disabled="
              busyToolId !== null ||
              profiles.length === 0 ||
              (selection[tool.id] ?? '') === ''
            "
            :aria-label="`${bindingFor(tool.id) ? '更换' : '绑定'} ${tool.display_name}`"
            @click="submitBind(tool.id)"
          >
            {{ bindingFor(tool.id) ? '更换绑定' : '绑定' }}
          </button>
          <button
            v-if="bindingFor(tool.id)"
            type="button"
            :disabled="busyToolId !== null"
            :aria-label="`解除 ${tool.display_name} 的绑定`"
            @click="emit('unbind', tool.id)"
          >
            解除绑定
          </button>
        </div>

        <p v-if="bindingFor(tool.id)" class="bindings__status">
          <template v-if="appliedAtFor(tool.id) !== null">
            已应用（{{ formatTime(appliedAtFor(tool.id) ?? '') }}<template
              v-if="snapshotIdFor(tool.id) !== null"
            >，快照 {{ snapshotIdFor(tool.id) }}</template>）
            <span v-if="needsReapply(tool.id)" class="bindings__pending">
              档案已修改，需重新应用
            </span>
          </template>
          <template v-else>已绑定，尚未应用</template>
        </p>
      </li>
    </ul>
    <p v-else-if="toolsError === null" class="bindings__empty">未发现已安装的工具。</p>

    <section v-if="orphanBindings.length > 0" class="bindings__orphans">
      <h3>已卸载但仍有绑定</h3>
      <ul class="bindings__list">
        <li v-for="binding in orphanBindings" :key="binding.tool_id" class="bindings__row">
          <div class="bindings__tool">
            <strong>{{ binding.tool_id }}</strong>
            <span class="bindings__unavailable">已不可用</span>
            <span class="bindings__current">
              当前档案：{{ profileName(binding.profile_id) }}
            </span>
          </div>
          <p class="bindings__status">
            <template v-if="appliedAtFor(binding.tool_id) !== null">
              已应用（{{ formatTime(appliedAtFor(binding.tool_id) ?? '') }}<template
                v-if="snapshotIdFor(binding.tool_id) !== null"
              >，快照 {{ snapshotIdFor(binding.tool_id) }}</template>）
              <span v-if="needsReapply(binding.tool_id)" class="bindings__pending">
                档案已修改，需重新应用
              </span>
            </template>
            <template v-else>已绑定，尚未应用</template>
          </p>
          <button
            type="button"
            :disabled="busyToolId !== null"
            :aria-label="`解除 ${binding.tool_id} 的绑定`"
            @click="emit('unbind', binding.tool_id)"
          >
            解除绑定
          </button>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.bindings {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  background: var(--color-surface);
}

.bindings__header h2 {
  margin: 0;
  font-size: var(--font-size-lg);
}

.bindings__hint,
.bindings__empty {
  margin: var(--space-1) 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.bindings__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.bindings__row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  border-top: 1px solid var(--color-border);
  padding-top: var(--space-2);
}

.bindings__tool,
.bindings__controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.bindings__current {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.bindings__unavailable {
  color: var(--color-danger);
  font-size: var(--font-size-sm);
}

.bindings__status {
  margin: 0;
  font-size: var(--font-size-sm);
}

.bindings__pending {
  margin: 0;
  color: var(--status-unconfigured-fg);
  font-size: var(--font-size-sm);
}

.bindings__error {
  margin: 0;
  color: var(--color-danger);
}

.bindings__orphans h3 {
  margin: var(--space-2) 0;
  font-size: var(--font-size-md);
}
</style>