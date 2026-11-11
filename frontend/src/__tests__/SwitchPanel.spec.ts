import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { BindingView, ProfileView } from '../api/profiles'
import type { SwitchApplyResponse, SwitchPreviewResponse } from '../api/switch'
import type { ToolView } from '../api/tools'
import SwitchPanel from '../components/SwitchPanel.vue'
import { getByRole, getByText } from './dom'

interface FetchCall {
  path: string
  method: string
  body: unknown
}

type Handler = (path: string, method: string, body: unknown) => Response | Promise<Response>

let calls: FetchCall[] = []

interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T) => void
}

function deferred<T>(): Deferred<T> {
  let resolve: (value: T) => void = () => undefined
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

function installFetch(handler: Handler): void {
  calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
      calls.push({ path, method, body })
      return handler(path, method, body)
    }),
  )
}

function callsTo(path: string, method: string): FetchCall[] {
  return calls.filter((call) => call.path === path && call.method === method)
}

function makeTool(overrides: Partial<ToolView> = {}): ToolView {
  return {
    id: 'claude-code',
    display_name: 'Claude Code',
    status: 'ok',
    installed: true,
    configured: true,
    version: null,
    provider: 'Anthropic',
    base_url: 'https://api.anthropic.com',
    model: 'claude-sonnet-4',
    is_third_party: false,
    config_path: '/home/me/.claude/settings.json',
    last_modified: null,
    has_secret: true,
    secret_preview: 'sk-a****cdef',
    warnings: [],
    capabilities: {
      read: true,
      write: true,
      sessions: false,
      launch: false,
      write_mode: 'managed_fields',
    },
    ...overrides,
  }
}

function makeProfile(overrides: Partial<ProfileView> = {}): ProfileView {
  return {
    id: 'profile-1',
    name: '主力档案',
    protocol: 'anthropic',
    base_url: 'https://relay.example.com',
    models: [
      { id: 'claude-sonnet-4', display_name: 'Sonnet' },
      { id: 'claude-opus-4', display_name: 'Opus' },
    ],
    created_at: '2026-11-10T12:00:00Z',
    updated_at: '2026-11-10T12:00:00Z',
    has_secret: true,
    secret_preview: 'sk-a****cdef',
    secret_backend: 'keyring',
    used_by: [],
    warnings: [],
    ...overrides,
  }
}

function makeBinding(profileId: string, toolId = 'claude-code'): BindingView {
  return {
    tool_id: toolId,
    profile_id: profileId,
    bound_at: '2026-11-10T12:00:00Z',
    active: true,
    applied_at: null,
    snapshot_id: null,
  }
}

function makeObservation(path: string) {
  return {
    path,
    exists: true,
    sha256: 'a'.repeat(64),
    size: 120,
    mtime_ns: 1,
  }
}

function makePreview(
  profile: ProfileView,
  overrides: Partial<SwitchPreviewResponse> = {},
): SwitchPreviewResponse {
  const path = '/home/me/.claude/settings.json'
  return {
    tool_id: 'claude-code',
    profile_id: profile.id,
    model: profile.models[0]?.id ?? null,
    available_models: profile.models,
    files: [
      {
        path,
        format: 'json',
        action: 'updated',
        before_sha256: 'a'.repeat(64),
        after_sha256: 'b'.repeat(64),
        before_size: 120,
        after_size: 140,
        changes: [
          {
            path: 'env.ANTHROPIC_BASE_URL',
            field: 'env.ANTHROPIC_BASE_URL',
            action: 'set',
            before: 'https://old.example.com',
            after: profile.base_url,
          },
        ],
      },
    ],
    blockers: [],
    warnings: [],
    restart_required: true,
    restart_message: 'Claude Code 需要重启后才会读取新的 settings.json',
    observations: [makeObservation(path)],
    preview_digest: 'c'.repeat(64),
    can_apply: true,
    ...overrides,
  }
}

function makeApplyResponse(
  profile: ProfileView,
  overrides: Partial<SwitchApplyResponse> = {},
): SwitchApplyResponse {
  return {
    tool_id: 'claude-code',
    profile_id: profile.id,
    snapshot_id: '11111111-1111-4111-8111-111111111111',
    audit_id: '22222222-2222-4222-8222-222222222222',
    files: [
      {
        path: '/home/me/.claude/settings.json',
        action: 'updated',
        sha256: 'b'.repeat(64),
        size: 140,
      },
    ],
    binding: {
      ...makeBinding(profile.id),
      applied_at: '2026-11-11T12:00:00Z',
      snapshot_id: '11111111-1111-4111-8111-111111111111',
    },
    warnings: [],
    restart_required: true,
    restart_message: 'Claude Code 需要重启后才会读取新的 settings.json',
    applied_at: '2026-11-11T12:00:00Z',
    ...overrides,
  }
}

function mountPanel(
  profiles: ProfileView[],
  bindings: BindingView[] = [],
  tool: ToolView = makeTool(),
) {
  return mount(SwitchPanel, {
    props: { tool, profiles, bindings },
    global: { plugins: [createPinia()] },
  })
}

describe('SwitchPanel', () => {
  beforeEach(() => {
    calls = []
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('defaults to the bound profile and its first model, then previews', async () => {
    const first = makeProfile()
    const bound = makeProfile({
      id: 'profile-2',
      name: '绑定档案',
      models: [{ id: 'claude-opus-4', display_name: 'Opus' }],
    })
    installFetch((path) => {
      if (path === '/api/switch/preview') {
        return jsonResponse(makePreview(bound))
      }
      throw new Error(`unexpected request: ${path}`)
    })

    const wrapper = mountPanel([first, bound], [makeBinding(bound.id)])
    await flushPromises()

    expect(getByRole(wrapper, 'combobox', { name: '选择档案' }).element).toHaveProperty(
      'value',
      bound.id,
    )
    expect(getByRole(wrapper, 'combobox', { name: '选择模型' }).element).toHaveProperty(
      'value',
      'claude-opus-4',
    )

    await getByRole(wrapper, 'button', { name: '预览改动' }).trigger('click')
    await flushPromises()

    expect(callsTo('/api/switch/preview', 'POST')[0]?.body).toEqual({
      tool_id: 'claude-code',
      profile_id: bound.id,
      model: 'claude-opus-4',
    })
    expect(getByRole(wrapper, 'dialog')).toBeTruthy()
    expect(wrapper.text()).toContain('/home/me/.claude/settings.json')
  })

  it('keeps the current model when the profile has no models', async () => {
    const profile = makeProfile({ models: [] })
    installFetch((path) => {
      if (path === '/api/switch/preview') {
        return jsonResponse(
          makePreview(profile, {
            model: null,
            available_models: [],
            warnings: [{ code: 'NO_MODELS', message: '档案没有模型清单，保持当前模型' }],
          }),
        )
      }
      throw new Error(`unexpected request: ${path}`)
    })

    const wrapper = mountPanel([profile])
    await flushPromises()

    expect(getByText(wrapper, '保持当前模型')).toBeTruthy()
    expect(getByRole(wrapper, 'combobox', { name: '选择模型' }).attributes('disabled')).toBeDefined()

    await getByRole(wrapper, 'button', { name: '预览改动' }).trigger('click')
    await flushPromises()

    expect(callsTo('/api/switch/preview', 'POST')[0]?.body).toEqual({
      tool_id: 'claude-code',
      profile_id: profile.id,
    })
    expect(wrapper.text()).toContain('NO_MODELS')
  })

  it('shows an empty state and disables preview when there are no profiles', async () => {
    const wrapper = mountPanel([])
    await flushPromises()

    expect(getByText(wrapper, '暂无可切换档案，请先在「档案」页新建。')).toBeTruthy()
    expect(getByRole(wrapper, 'button', { name: '预览改动' }).attributes('disabled')).toBeDefined()
    expect(calls).toHaveLength(0)
  })

  it('cancels the preview without sending an apply request', async () => {
    const profile = makeProfile()
    installFetch((path) => {
      if (path === '/api/switch/preview') {
        return jsonResponse(makePreview(profile))
      }
      throw new Error(`unexpected request: ${path}`)
    })
    const wrapper = mountPanel([profile])
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '预览改动' }).trigger('click')
    await flushPromises()
    await getByRole(wrapper, 'button', { name: '取消' }).trigger('click')
    await flushPromises()

    expect(callsTo('/api/switch/apply', 'POST')).toHaveLength(0)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('已应用档案配置')
  })

  it('applies the preview and emits the applied result with snapshot and restart details', async () => {
    const profile = makeProfile()
    const applied = makeApplyResponse(profile)
    installFetch((path) => {
      if (path === '/api/switch/preview') {
        return jsonResponse(makePreview(profile))
      }
      if (path === '/api/switch/apply') {
        return jsonResponse(applied)
      }
      throw new Error(`unexpected request: ${path}`)
    })
    const wrapper = mountPanel([profile])
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '预览改动' }).trigger('click')
    await flushPromises()
    await getByRole(wrapper, 'button', { name: '确认应用' }).trigger('click')
    await flushPromises()

    expect(callsTo('/api/switch/apply', 'POST')[0]?.body).toEqual({
      tool_id: 'claude-code',
      profile_id: profile.id,
      model: 'claude-sonnet-4',
      preview_digest: 'c'.repeat(64),
      observations: [makeObservation('/home/me/.claude/settings.json')],
    })
    expect(wrapper.emitted('applied')).toHaveLength(1)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('已应用档案配置')
    expect(wrapper.text()).toContain(applied.snapshot_id)
    expect(wrapper.text()).toContain(applied.restart_message)
  })

  it('does not send a second apply request while the first is in flight', async () => {
    const profile = makeProfile()
    const pendingApply = deferred<Response>()
    installFetch((path) => {
      if (path === '/api/switch/preview') {
        return jsonResponse(makePreview(profile))
      }
      if (path === '/api/switch/apply') {
        return pendingApply.promise
      }
      throw new Error(`unexpected request: ${path}`)
    })
    const wrapper = mountPanel([profile])
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '预览改动' }).trigger('click')
    await flushPromises()
    const confirm = getByRole(wrapper, 'button', { name: '确认应用' })
    await confirm.trigger('click')
    await confirm.trigger('click')
    await flushPromises()

    expect(callsTo('/api/switch/apply', 'POST')).toHaveLength(1)

    pendingApply.resolve(jsonResponse(makeApplyResponse(profile)))
    await flushPromises()

    expect(wrapper.text()).toContain('已应用档案配置')
  })

  it('keeps the dialog open on conflict and re-previews on request', async () => {
    const profile = makeProfile()
    const conflict = {
      path: '/home/me/.claude/settings.json',
      reason: 'CONTENT_CHANGED',
      expected: makeObservation('/home/me/.claude/settings.json'),
      actual: {
        ...makeObservation('/home/me/.claude/settings.json'),
        sha256: 'd'.repeat(64),
      },
    }
    installFetch((path) => {
      if (path === '/api/switch/preview') {
        return jsonResponse(makePreview(profile))
      }
      if (path === '/api/switch/apply') {
        return jsonResponse(
          {
            code: 'WRITE_CONFLICT',
            message: '1 个文件在预览后发生变化, 已拒绝写入',
            details: { conflicts: [conflict] },
          },
          409,
        )
      }
      throw new Error(`unexpected request: ${path}`)
    })
    const wrapper = mountPanel([profile])
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '预览改动' }).trigger('click')
    await flushPromises()
    await getByRole(wrapper, 'button', { name: '确认应用' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'dialog')).toBeTruthy()
    expect(getByRole(wrapper, 'alert').text()).toContain('已拒绝写入')
    expect(wrapper.text()).toContain(conflict.path)
    expect(wrapper.text()).toContain('文件内容已变化')

    await getByRole(wrapper, 'button', { name: '重新预览' }).trigger('click')
    await flushPromises()

    expect(callsTo('/api/switch/preview', 'POST')).toHaveLength(2)
    expect(getByRole(wrapper, 'dialog')).toBeTruthy()
  })

  it('shows a slow preview in progress and blocks duplicate previews', async () => {
    const profile = makeProfile()
    const pendingPreview = deferred<Response>()
    installFetch((path) => {
      if (path === '/api/switch/preview') {
        return pendingPreview.promise
      }
      throw new Error(`unexpected request: ${path}`)
    })
    const wrapper = mountPanel([profile])
    await flushPromises()

    const previewButton = getByRole(wrapper, 'button', { name: '预览改动' })
    await previewButton.trigger('click')
    await flushPromises()

    expect(getByText(wrapper, '正在生成预览…')).toBeTruthy()
    expect(
      getByRole(wrapper, 'button', { name: '正在预览…' }).attributes('disabled'),
    ).toBeDefined()

    await getByRole(wrapper, 'button', { name: '正在预览…' }).trigger('click')
    expect(callsTo('/api/switch/preview', 'POST')).toHaveLength(1)

    pendingPreview.resolve(jsonResponse(makePreview(profile)))
    await flushPromises()

    expect(getByRole(wrapper, 'dialog')).toBeTruthy()
  })

  it('reports a timeout without opening a preview or claiming success', async () => {
    const profile = makeProfile()
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_path: string, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => reject(new Error('aborted')))
          }),
      ),
    )
    const wrapper = mountPanel([profile])
    await wrapper.vm.$nextTick()

    await getByRole(wrapper, 'button', { name: '预览改动' }).trigger('click')
    await vi.advanceTimersByTimeAsync(10_000)
    await wrapper.vm.$nextTick()

    expect(getByRole(wrapper, 'alert').text()).toContain('请求超时，请稍后重试')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('已应用档案配置')
  })
})
