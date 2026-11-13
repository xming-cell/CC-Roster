import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { AppearanceOverride } from '../api/appearances'
import type { ToolView } from '../api/tools'
import AppearanceEditor from '../components/AppearanceEditor.vue'
import { useAppearancesStore } from '../stores/appearances'
import { getByRole } from './dom'

const tool: ToolView = {
  id: 'claude-code',
  display_name: 'Claude Code',
  status: 'ok',
  installed: true,
  configured: true,
  version: null,
  provider: 'Anthropic',
  base_url: null,
  model: 'claude-sonnet-4',
  is_third_party: false,
  config_path: null,
  last_modified: null,
  has_secret: false,
  secret_preview: null,
  warnings: [],
  capabilities: {
    read: true,
    write: false,
    sessions: false,
    launch: false,
    write_mode: 'none',
  },
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

function mountEditor(
  pinia = createPinia(),
  override?: AppearanceOverride,
  attachTo?: Element,
) {
  const wrapper = mount(AppearanceEditor, {
    props: { tool, override },
    global: { plugins: [pinia] },
    attachTo,
  })
  return { wrapper, pinia, store: useAppearancesStore(pinia) }
}

describe('AppearanceEditor', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('supports labelled keyboard-focusable controls and cancel without saving', async () => {
    const fetchMock = vi.fn<(path: string, init?: RequestInit) => Promise<Response>>()
    vi.stubGlobal('fetch', fetchMock)
    const { wrapper } = mountEditor(createPinia(), undefined, document.body)

    await getByRole(wrapper, 'button', { name: '编辑外观' }).trigger('click')

    expect(wrapper.find('input[aria-label="强调色"]').exists()).toBe(true)
    expect(wrapper.find('input[aria-label="聊天背景色"]').exists()).toBe(true)
    expect(getByRole(wrapper, 'combobox', { name: '气泡样式' }).exists()).toBe(true)
    const saveButton = getByRole(wrapper, 'button', { name: '保存' })
    const saveButtonElement = saveButton.element as HTMLButtonElement
    saveButtonElement.focus()
    expect(document.activeElement).toBe(saveButtonElement)

    await wrapper.find('input[aria-label="强调色"]').setValue('#123456')
    await getByRole(wrapper, 'button', { name: '取消' }).trigger('click')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(getByRole(wrapper, 'button', { name: '编辑外观' }).exists()).toBe(true)
    wrapper.unmount()
  })

  it('saves an override and reports failed saves without closing the editor', async () => {
    let failSave = false
    const fetchMock = vi.fn<(path: string, init?: RequestInit) => Promise<Response>>(
      (path, init) => {
        if (init?.method === 'PUT') {
          if (failSave) {
            return Promise.resolve(
              jsonResponse({ code: 'APPEARANCE_WRITE_FAILED', message: '磁盘写入失败' }, 500),
            )
          }
          const appearance = JSON.parse(String(init.body)) as AppearanceOverride
          return Promise.resolve(
            jsonResponse({
              tool_id: 'claude-code',
              ...appearance,
              accent_color: appearance.accent_color?.toUpperCase() ?? null,
              background_color: appearance.background_color?.toUpperCase() ?? null,
            }),
          )
        }
        return Promise.resolve(jsonResponse({ schema_version: 1, appearances: {} }))
      },
    )
    vi.stubGlobal('fetch', fetchMock)
    const { wrapper, store } = mountEditor()

    await getByRole(wrapper, 'button', { name: '编辑外观' }).trigger('click')
    await wrapper.find('input[aria-label="强调色"]').setValue('#123456')
    await wrapper.find('input[aria-label="聊天背景色"]').setValue('#ABCDEF')
    await getByRole(wrapper, 'combobox', { name: '气泡样式' }).setValue('compact')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(store.appearances['claude-code']).toEqual({
      accent_color: '#123456',
      background_color: '#ABCDEF',
      bubble_preset: 'compact',
    })
    expect(getByRole(wrapper, 'button', { name: '编辑外观' }).exists()).toBe(true)

    failSave = true
    await getByRole(wrapper, 'button', { name: '编辑外观' }).trigger('click')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(getByRole(wrapper, 'alert').text()).toContain('磁盘写入失败')
    expect(getByRole(wrapper, 'button', { name: '保存' }).exists()).toBe(true)
  })

  it('cancels reset on confirmation decline and resets only the current tool', async () => {
    const existing = { accent_color: '#123456', background_color: null, bubble_preset: null }
    const fetchMock = vi.fn<(path: string, init?: RequestInit) => Promise<Response>>(
      (path, init) =>
        Promise.resolve(
          init?.method === 'DELETE'
            ? jsonResponse({ tool_id: 'claude-code', reset: true })
            : jsonResponse({ schema_version: 1, appearances: {} }),
        ),
    )
    vi.stubGlobal('fetch', fetchMock)
    const { wrapper, store } = mountEditor()
    store.appearances = {
      'claude-code': existing,
      'codex-cli': { accent_color: null, background_color: '#ABCDEF', bubble_preset: 'soft' },
    }
    const other = store.appearances['codex-cli']
    const confirm = vi.fn<(message?: string) => boolean>().mockReturnValue(false)
    vi.stubGlobal('confirm', confirm)

    await getByRole(wrapper, 'button', { name: '恢复默认' }).trigger('click')
    expect(fetchMock).not.toHaveBeenCalled()
    expect(store.appearances['claude-code']).toEqual(existing)

    confirm.mockReturnValue(true)
    await getByRole(wrapper, 'button', { name: '恢复默认' }).trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(store.appearances['claude-code']).toBeUndefined()
    expect(store.appearances['codex-cli']).toEqual(other)
  })
})
