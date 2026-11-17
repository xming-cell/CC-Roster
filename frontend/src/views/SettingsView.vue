<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import type { AppearanceOverride, BubblePreset } from '../api/appearances'
import { errorText } from '../utils/profileDisplay'
import { useAppearancesStore } from '../stores/appearances'
import { useSettingsStore } from '../stores/settings'
import { useToolsStore } from '../stores/tools'

const settingsStore = useSettingsStore()
const appearancesStore = useAppearancesStore()
const toolsStore = useToolsStore()
const { settings, loading, loaded, error, readOnly } = storeToRefs(settingsStore)
const { appearances, error: appearanceLoadError } = storeToRefs(appearancesStore)
const { tools } = storeToRefs(toolsStore)

const selectedToolId = ref<string | null>(null)
const accentColor = ref('#2563EB')
const backgroundColor = ref('#FFFFFF')
const bubblePreset = ref<BubblePreset>('soft')
const appearanceSaving = ref(false)
const appearanceStatus = ref<string | null>(null)
const appearanceError = ref<string | null>(null)
const hotkeyDraft = ref('')
const hotkeyBusy = ref(false)
const hotkeyStatus = ref<string | null>(null)
const hotkeyError = ref<string | null>(null)
const capabilityBusy = ref<string | null>(null)

const accentOptions = ['#2563EB', '#06B6D4', '#16A34A', '#F59E0B', '#DC2626']
const backgroundOptions = ['#FFFFFF', '#F8FAFC', '#F1F5F9', '#EFF6FF']
const presetOptions: { value: BubblePreset; label: string; hint: string }[] = [
  { value: 'soft', label: '柔和', hint: '12px 圆角' },
  { value: 'rounded', label: '圆角', hint: '16px 圆角' },
  { value: 'compact', label: '紧凑', hint: '10px 内边距' },
]

const selectedTool = computed(() => tools.value.find((tool) => tool.id === selectedToolId.value) ?? null)
const canEditAppearance = computed(
  () => selectedToolId.value !== null && !readOnly.value && !appearanceSaving.value,
)
const capabilities = computed(() => settings.value?.capabilities ?? { tray: false, hotkey: false, autostart: false })

function savedAppearance(toolId: string): AppearanceOverride {
  return appearances.value[toolId] ?? {
    accent_color: '#2563EB',
    background_color: '#FFFFFF',
    bubble_preset: 'soft',
  }
}

function applyAppearance(toolId: string | null): void {
  if (toolId === null) {
    return
  }
  const saved = savedAppearance(toolId)
  accentColor.value = saved.accent_color ?? '#2563EB'
  backgroundColor.value = saved.background_color ?? '#FFFFFF'
  bubblePreset.value = saved.bubble_preset ?? 'soft'
  appearanceStatus.value = null
  appearanceError.value = null
}

watch(selectedToolId, (toolId) => {
  applyAppearance(toolId)
})

watch(
  () => settings.value?.hotkey,
  (value) => {
    hotkeyDraft.value = value ?? ''
  },
  { immediate: true },
)

async function loadPage(): Promise<void> {
  await Promise.all([settingsStore.load(), toolsStore.fetchTools(), appearancesStore.load()])
  if (selectedToolId.value === null && tools.value.length > 0) {
    selectedToolId.value = tools.value[0]?.id ?? null
  }
  applyAppearance(selectedToolId.value)
}

onMounted(() => {
  void loadPage()
})

async function persistAppearance(patch: Partial<AppearanceOverride>): Promise<void> {
  const toolId = selectedToolId.value
  if (toolId === null || readOnly.value || appearanceSaving.value) {
    return
  }
  const before: AppearanceOverride = {
    accent_color: accentColor.value,
    background_color: backgroundColor.value,
    bubble_preset: bubblePreset.value,
  }
  const next: AppearanceOverride = { ...before, ...patch }
  accentColor.value = next.accent_color ?? accentColor.value
  backgroundColor.value = next.background_color ?? backgroundColor.value
  bubblePreset.value = next.bubble_preset ?? bubblePreset.value
  appearanceSaving.value = true
  appearanceError.value = null
  appearanceStatus.value = '保存中…'
  try {
    await appearancesStore.save(toolId, next)
    appearanceStatus.value = '已保存'
  } catch (caught) {
    accentColor.value = before.accent_color ?? accentColor.value
    backgroundColor.value = before.background_color ?? backgroundColor.value
    bubblePreset.value = before.bubble_preset ?? bubblePreset.value
    appearanceStatus.value = null
    appearanceError.value = errorText(caught, '外观保存失败')
  } finally {
    appearanceSaving.value = false
  }
}

async function resetAppearance(): Promise<void> {
  const toolId = selectedToolId.value
  if (toolId === null || readOnly.value || appearanceSaving.value) {
    return
  }
  appearanceSaving.value = true
  appearanceError.value = null
  appearanceStatus.value = '正在恢复默认…'
  try {
    await appearancesStore.reset(toolId)
    accentColor.value = '#2563EB'
    backgroundColor.value = '#FFFFFF'
    bubblePreset.value = 'soft'
    appearanceStatus.value = '已恢复默认'
  } catch (caught) {
    appearanceStatus.value = null
    appearanceError.value = errorText(caught, '恢复默认失败')
  } finally {
    appearanceSaving.value = false
  }
}

async function toggleReadOnly(): Promise<void> {
  if (capabilityBusy.value !== null) {
    return
  }
  capabilityBusy.value = 'read_only'
  try {
    await settingsStore.update({ read_only: !readOnly.value })
  } catch {
    // store.error 已提供可读原因
  } finally {
    capabilityBusy.value = null
  }
}

async function toggleAutostart(): Promise<void> {
  if (capabilityBusy.value !== null || settings.value === null) {
    return
  }
  capabilityBusy.value = 'autostart'
  try {
    await settingsStore.update({ autostart: !settings.value.autostart })
  } catch {
    // store.error 已提供可读原因
  } finally {
    capabilityBusy.value = null
  }
}

async function saveHotkey(): Promise<void> {
  if (hotkeyBusy.value) {
    return
  }
  hotkeyBusy.value = true
  hotkeyStatus.value = null
  hotkeyError.value = null
  try {
    await settingsStore.update({ hotkey: hotkeyDraft.value.trim() })
    hotkeyStatus.value = '快捷键已保存'
  } catch (caught) {
    hotkeyError.value = errorText(caught, '快捷键保存失败')
  } finally {
    hotkeyBusy.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <header class="page-header">
      <div><h1>设置</h1><p>全局偏好、桌面能力与本地数据</p></div>
      <span class="page-header__meta">{{ readOnly ? '只读模式' : '可写模式' }}</span>
    </header>

    <div class="settings-page__body">
      <div v-if="loading && !loaded" class="settings-state" role="status">正在读取设置…</div>
      <div v-else-if="error && settings === null" class="settings-state settings-state--danger" role="alert">
        <strong>设置读取失败</strong><span>{{ error }}</span>
        <button class="button button--secondary" type="button" @click="loadPage">重试</button>
      </div>
      <template v-else>
        <div class="settings-column">
          <section class="settings-card" aria-labelledby="appearance-title">
            <header class="settings-card__head">
              <div><h2 id="appearance-title">外观偏好</h2><p>按工具保存，只影响对话气泡与强调色</p></div>
              <select v-model="selectedToolId" class="settings-select" aria-label="选择外观工具">
                <option v-if="tools.length === 0" :value="null">没有可用工具</option>
                <option v-for="tool in tools" :key="tool.id" :value="tool.id">{{ tool.display_name }}</option>
              </select>
            </header>

            <div v-if="appearanceLoadError" class="settings-inline settings-inline--danger" role="alert">{{ appearanceLoadError }}</div>
            <div v-if="readOnly" class="settings-inline settings-inline--warning" role="status">
              只读模式已开启，外观偏好暂不可修改。先在上方“运行与桌面”中关闭只读。
            </div>

            <div class="appearance-layout">
              <div class="appearance-controls">
                <fieldset class="appearance-field" :disabled="!canEditAppearance">
                  <legend>强调色</legend>
                  <div class="appearance-swatches">
                    <button
                      v-for="color in accentOptions"
                      :key="color"
                      class="appearance-swatch"
                      :class="{ 'appearance-swatch--active': accentColor === color }"
                      type="button"
                      :aria-label="'强调色 ' + color"
                      :style="{ background: color }"
                      @click="persistAppearance({ accent_color: color })"
                    ></button>
                  </div>
                </fieldset>

                <fieldset class="appearance-field" :disabled="!canEditAppearance">
                  <legend>背景色</legend>
                  <div class="appearance-swatches">
                    <button
                      v-for="color in backgroundOptions"
                      :key="color"
                      class="appearance-swatch appearance-swatch--light"
                      :class="{ 'appearance-swatch--active': backgroundColor === color }"
                      type="button"
                      :aria-label="'背景色 ' + color"
                      :style="{ background: color }"
                      @click="persistAppearance({ background_color: color })"
                    ></button>
                  </div>
                </fieldset>

                <fieldset class="appearance-field" :disabled="!canEditAppearance">
                  <legend>气泡样式</legend>
                  <div class="appearance-presets">
                    <button
                      v-for="preset in presetOptions"
                      :key="preset.value"
                      class="appearance-preset"
                      :class="{ 'appearance-preset--active': bubblePreset === preset.value }"
                      type="button"
                      @click="persistAppearance({ bubble_preset: preset.value })"
                    >
                      <strong>{{ preset.label }}</strong><span>{{ preset.hint }}</span>
                    </button>
                  </div>
                </fieldset>
                <div class="appearance-status" role="status">
                  <span>{{ appearanceStatus ?? '修改后即时保存' }}</span>
                  <button class="text-button" type="button" :disabled="!canEditAppearance" @click="resetAppearance">恢复默认</button>
                </div>
              </div>

              <div class="appearance-preview" :style="{ background: backgroundColor }">
                <span class="appearance-preview__label">实时预览</span>
                <div class="appearance-preview__user" :style="{ background: accentColor }">帮我检查这段配置</div>
                <div class="appearance-preview__assistant" :class="'appearance-preview__assistant--' + bubblePreset">
                  配置结构正常。建议先预览影响范围，再应用到工具。
                </div>
                <span class="appearance-preview__meta">{{ selectedTool?.display_name ?? '未选择工具' }}</span>
              </div>
            </div>
            <p v-if="appearanceError" class="settings-error" role="alert">{{ appearanceError }}</p>
          </section>

          <section class="settings-card" aria-labelledby="runtime-title">
            <header class="settings-card__head">
              <div><h2 id="runtime-title">运行与桌面</h2><p>只读、快捷键与开机自启按当前平台能力显示</p></div>
              <span class="settings-badge">{{ capabilities.tray ? '桌面能力可用' : '浏览器模式' }}</span>
            </header>

            <div class="runtime-row">
              <div><strong>只读模式</strong><p>开启后拒绝所有配置写入，并禁用写入口</p></div>
              <button class="switch" :class="{ 'switch--on': readOnly }" type="button" role="switch" aria-label="只读模式" :aria-checked="readOnly" :disabled="capabilityBusy !== null" @click="toggleReadOnly">
                <span></span>
              </button>
            </div>

            <div v-if="capabilities.hotkey" class="runtime-row">
              <div><strong>全局快捷键</strong><p>从任意应用唤起 CC-Roster 主窗口</p></div>
              <div class="runtime-hotkey">
                <input v-model="hotkeyDraft" class="settings-input" type="text" aria-label="全局快捷键" />
                <button class="button button--secondary" type="button" :disabled="hotkeyBusy" @click="saveHotkey">保存</button>
              </div>
            </div>

            <div v-if="capabilities.autostart" class="runtime-row">
              <div><strong>开机自启</strong><p>登录系统后在后台启动，可随时撤销</p></div>
              <button class="switch" :class="{ 'switch--on': settings?.autostart === true }" type="button" role="switch" aria-label="开机自启" :aria-checked="settings?.autostart === true" :disabled="capabilityBusy !== null" @click="toggleAutostart">
                <span></span>
              </button>
            </div>

            <div v-if="!capabilities.hotkey || !capabilities.autostart" class="settings-inline settings-inline--warning">
              当前平台不支持的能力已隐藏，不会显示无效开关。
            </div>
            <p v-if="hotkeyStatus" class="settings-success" role="status">{{ hotkeyStatus }}</p>
            <p v-if="hotkeyError" class="settings-error" role="alert">{{ hotkeyError }}</p>
            <p v-if="error" class="settings-error" role="alert">{{ error }}</p>
          </section>
        </div>

        <div class="settings-column">
          <section class="settings-card" aria-labelledby="privacy-title">
            <header class="settings-card__head">
              <div><h2 id="privacy-title">本地数据与隐私</h2><p>所有配置、会话与审计都写入本机目录</p></div>
              <span class="settings-badge settings-badge--success">仅存本机</span>
            </header>
            <div class="data-path"><span>数据目录</span><code>%APPDATA%\CC-Roster</code></div>
            <dl class="privacy-list">
              <div><dt>包含内容</dt><dd>供应商配置、会话记录、配置快照、审计记录与外观偏好。</dd></div>
              <div><dt>日志</dt><dd>logs/app.log · 按日轮转，保留 7 天；不含密钥或文件原文。</dd></div>
              <div><dt>脱敏边界</dt><dd>密钥只进入本机密钥库。列表、日志与审计只显示掩码摘要，不记录完整请求体或文件原文。</dd></div>
              <div><dt>清除方式</dt><dd>退出应用后删除上述数据目录即可；工具自身的配置文件不受影响。</dd></div>
            </dl>
            <div class="privacy-note">密钥不会进入日志、审计或界面回显。</div>
          </section>

          <section class="settings-card" aria-labelledby="capability-title">
            <header class="settings-card__head">
              <div><h2 id="capability-title">当前平台能力</h2><p>由本机桌面能力探测得出</p></div>
              <span class="settings-badge settings-badge--success">已检测</span>
            </header>
            <ul class="capability-list">
              <li><span>系统托盘</span><strong :class="{ 'capability--off': !capabilities.tray }">{{ capabilities.tray ? '可用' : '不可用' }}</strong></li>
              <li><span>全局快捷键</span><strong :class="{ 'capability--off': !capabilities.hotkey }">{{ capabilities.hotkey ? '可用' : '不可用' }}</strong></li>
              <li><span>开机自启</span><strong :class="{ 'capability--off': !capabilities.autostart }">{{ capabilities.autostart ? '可用' : '不可用' }}</strong></li>
            </ul>
            <p class="settings-footnote">不可用的平台能力会隐藏或明确标注，不显示无效开关。</p>
          </section>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.settings-page { display: flex; flex-direction: column; height: 100%; min-height: 0; background: var(--color-bg); }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-lg); min-height: 65px; padding: var(--space-md) var(--space-xl); border-bottom: 1px solid var(--color-border); background: var(--color-surface); }
.page-header h1 { margin: 0; font-size: var(--font-size-xl); line-height: var(--line-height-tight); }
.page-header p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.page-header__meta { padding: 3px 8px; border-radius: 999px; background: var(--color-bg-subtle); color: var(--color-info-fg); font-size: var(--font-size-xs); font-weight: 600; }
.settings-page__body { display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(320px, 1fr); gap: var(--space-lg); min-height: 0; padding: var(--space-xl); overflow-y: auto; }
.settings-column { display: flex; flex-direction: column; gap: var(--space-lg); min-width: 0; }
.settings-card { padding: var(--space-lg); border: 1px solid var(--color-border-card); border-radius: var(--radius-lg); background: var(--color-surface); }
.settings-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-lg); margin-bottom: var(--space-lg); }
.settings-card__head h2 { margin: 0; font-size: var(--font-size-md); }
.settings-card__head p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.settings-select { max-width: 180px; padding: 6px 10px; border: 1px solid var(--color-border-control); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text); font: inherit; font-size: var(--font-size-xs); }
.settings-badge { padding: 3px 8px; border-radius: 999px; background: var(--color-bg-subtle); color: var(--color-info-fg); font-size: 10px; font-weight: 600; white-space: nowrap; }
.settings-badge--success { background: var(--color-success-bg); color: var(--color-success-fg); }
.settings-state { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-sm); color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.settings-state--danger { color: var(--color-danger-fg); }
.appearance-layout { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: var(--space-lg); }
.appearance-controls { display: flex; flex-direction: column; gap: var(--space-lg); min-width: 0; }
.appearance-field { margin: 0; padding: 0; border: 0; }
.appearance-field legend { margin-bottom: var(--space-sm); color: var(--color-info-fg); font-size: var(--font-size-xs); font-weight: 600; }
.appearance-field:disabled { opacity: 0.55; }
.appearance-swatches { display: flex; gap: var(--space-sm); }
.appearance-swatch { width: 24px; height: 24px; padding: 0; border: 2px solid transparent; border-radius: 50%; cursor: pointer; }
.appearance-swatch--light { border-color: var(--color-border-control); }
.appearance-swatch--active { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.appearance-presets { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-sm); }
.appearance-preset { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; padding: var(--space-sm); border: 1px solid var(--color-border-card); border-radius: var(--radius-md); background: var(--color-surface); text-align: left; cursor: pointer; }
.appearance-preset strong { font-size: var(--font-size-xs); }
.appearance-preset span { color: var(--color-text-muted); font-size: 10px; }
.appearance-preset--active { border-color: var(--color-border-selected); background: var(--color-bg-selected); }
.appearance-status { display: flex; align-items: center; justify-content: space-between; gap: var(--space-md); color: var(--color-text-muted); font-size: 10px; }
.text-button { padding: 0; border: 0; background: transparent; color: var(--color-primary); font-size: 10px; font-weight: 600; cursor: pointer; }
.text-button:disabled { color: var(--color-text-muted); cursor: not-allowed; }
.appearance-preview { display: flex; flex-direction: column; gap: var(--space-sm); min-height: 190px; padding: var(--space-md); border: 1px solid var(--color-border-card); border-radius: var(--radius-lg); }
.appearance-preview__label { color: var(--color-text-secondary); font-size: 10px; font-weight: 600; }
.appearance-preview__user { align-self: flex-end; max-width: 90%; padding: 8px 10px; border-radius: 12px; color: var(--color-surface); font-size: 10px; }
.appearance-preview__assistant { padding: 10px; border: 1px solid var(--color-border-card); background: var(--color-surface); color: var(--color-info-fg); font-size: 10px; line-height: 1.6; }
.appearance-preview__assistant--soft { border-radius: 12px; }
.appearance-preview__assistant--rounded { border-radius: 16px; }
.appearance-preview__assistant--compact { padding: 6px 8px; border-radius: 10px; }
.appearance-preview__meta { margin-top: auto; color: var(--color-text-muted); font-size: 9px; }
.runtime-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-lg); padding: var(--space-md) 0; border-top: 1px solid var(--color-bg-subtle); }
.runtime-row > div:first-child { min-width: 0; }
.runtime-row strong { font-size: var(--font-size-sm); }
.runtime-row p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: 10px; }
.runtime-hotkey { display: flex; align-items: center; gap: var(--space-sm); }
.settings-input { width: 150px; padding: 6px 9px; border: 1px solid var(--color-border-control); border-radius: var(--radius-md); font: inherit; font-family: var(--font-mono); font-size: var(--font-size-xs); }
.switch { position: relative; width: 38px; height: 22px; flex: none; padding: 0; border: 0; border-radius: 999px; background: var(--color-icon-disabled); cursor: pointer; }
.switch span { position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: var(--color-surface); transition: transform 120ms ease-out; }
.switch--on { background: var(--color-primary); }
.switch--on span { transform: translateX(16px); }
.switch:disabled { cursor: not-allowed; opacity: 0.65; }
.settings-inline { margin-bottom: var(--space-md); padding: var(--space-sm) var(--space-md); border-radius: var(--radius-md); font-size: var(--font-size-xs); }
.settings-inline--warning { background: var(--color-warning-bg); color: var(--color-warning-fg); }
.settings-inline--danger { background: var(--color-danger-bg); color: var(--color-danger-fg); }
.settings-error { margin: var(--space-sm) 0 0; color: var(--color-danger-fg); font-size: var(--font-size-xs); }
.settings-success { margin: var(--space-sm) 0 0; color: var(--color-success-fg); font-size: var(--font-size-xs); }
.data-path { display: flex; flex-direction: column; gap: 3px; padding: var(--space-md); border-radius: var(--radius-md); background: var(--color-bg); }
.data-path span { color: var(--color-text-secondary); font-size: 9px; font-weight: 600; }
.data-path code { color: var(--color-info-fg); font-family: var(--font-mono); font-size: 10px; overflow-wrap: anywhere; }
.privacy-list { display: flex; flex-direction: column; gap: var(--space-md); margin: var(--space-lg) 0; }
.privacy-list div { display: flex; flex-direction: column; gap: 3px; }
.privacy-list dt { color: var(--color-info-fg); font-size: 10px; font-weight: 600; }
.privacy-list dd { margin: 0; color: var(--color-text-secondary); font-size: var(--font-size-xs); line-height: var(--line-height-relaxed); }
.privacy-note { padding: var(--space-sm) var(--space-md); border-radius: var(--radius-md); background: var(--color-bg-selected); color: var(--color-primary-hover); font-size: 10px; font-weight: 600; }
.capability-list { margin: 0; padding: 0; list-style: none; }
.capability-list li { display: flex; align-items: center; justify-content: space-between; gap: var(--space-md); padding: var(--space-sm) 0; border-bottom: 1px solid var(--color-bg-subtle); font-size: var(--font-size-xs); }
.capability-list strong { color: var(--color-success-fg); }
.capability-list .capability--off { color: var(--color-text-muted); }
.settings-footnote { margin: var(--space-md) 0 0; color: var(--color-text-muted); font-size: 10px; }
@media (max-width: 1080px) { .settings-page__body { grid-template-columns: 1fr; } .appearance-layout { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .page-header { align-items: flex-start; } .settings-page__body { padding: var(--space-lg); } .runtime-row { align-items: flex-start; flex-direction: column; } .runtime-hotkey { width: 100%; } .settings-input { flex: 1; } }
</style>
