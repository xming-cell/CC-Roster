import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type {
  BindingView,
  ProfileListResponse,
  ProfileView,
  SecretStoreStatus,
} from '../api/profiles'
import type { ToolView } from '../api/tools'
import ProfilesView from '../views/ProfilesView.vue'
import { getAllByRole, getByRole, getByText } from './dom'

interface FetchCall {
  path: string
  method: string
  body: unknown
}

type Handler = (path: string, method: string, body: unknown) => Response | Promise<Response>

let calls: FetchCall[] = []

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

const keyringStatus: SecretStoreStatus = {
  backend: 'keyring',
  fallback: false,
  message: null,
}

function makeProfile(overrides: Partial<ProfileView> = {}): ProfileView {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    name: 'Anthropic 主力',
    protocol: 'anthropic',
    base_url: 'https://api.anthropic.com/v1',
    models: [{ id: 'claude-sonnet-4', display_name: 'Sonnet' }],
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
      write: false,
      sessions: false,
      launch: false,
      write_mode: 'none',
    },
    ...overrides,
  }
}

function profilesBody(
  profiles: ProfileView[],
  bindings: BindingView[] = [],
  secretStore: SecretStoreStatus = keyringStatus,
  warnings: ProfileListResponse['warnings'] = [],
): ProfileListResponse {
  return { profiles, bindings, secret_store: secretStore, warnings }
}

const appliedSnapshotId = '44444444-4444-4444-8444-444444444444'

function makeBinding(profileId: string, toolId = 'claude-code'): BindingView {
  return {
    tool_id: toolId,
    profile_id: profileId,
    bound_at: '2026-11-10T12:00:00Z',
    active: false,
    applied_at: null,
    snapshot_id: null,
  }
}

function makeAppliedBinding(
  profileId: string,
  toolId = 'claude-code',
): BindingView {
  return {
    ...makeBinding(profileId, toolId),
    active: true,
    applied_at: '2026-11-10T13:00:00Z',
    snapshot_id: appliedSnapshotId,
  }
}

function mountProfiles() {
  return mount(ProfilesView, { global: { plugins: [createPinia()] } })
}

function requestCalls(method: string, path: string): FetchCall[] {
  return calls.filter((call) => call.method === method && call.path === path)
}

describe('ProfilesView', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading status while the profile list is pending', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>(() => undefined)),
    )

    const wrapper = mountProfiles()
    await flushPromises()

    expect(getByText(wrapper, '正在加载档案…')).toBeTruthy()
  })

  it('lists profiles with protocol, models, secret preview and used_by tools', async () => {
    const profile = makeProfile({
      models: [
        { id: 'claude-sonnet-4', display_name: 'Sonnet' },
        { id: 'claude-opus-4', display_name: null },
      ],
      used_by: [
        { tool_id: 'claude-code', display_name: 'Claude Code', installed: true },
        { tool_id: 'codex-cli', display_name: 'Codex CLI', installed: true },
      ],
    })
    installFetch((path) => {
      if (path === '/api/profiles') {
        return jsonResponse(profilesBody([profile], [makeBinding(profile.id)]))
      }
      return jsonResponse({ tools: [], warnings: [] })
    })

    const wrapper = mountProfiles()
    await flushPromises()

    expect(getByRole(wrapper, 'heading', { name: '档案' })).toBeTruthy()
    expect(getByRole(wrapper, 'heading', { name: 'Anthropic 主力' })).toBeTruthy()
    expect(getByText(wrapper, 'Anthropic 协议')).toBeTruthy()
    expect(getByText(wrapper, 'https://api.anthropic.com/v1')).toBeTruthy()
    expect(getByText(wrapper, '2 个模型')).toBeTruthy()
    expect(getByText(wrapper, 'sk-a****cdef（系统钥匙串）')).toBeTruthy()
    expect(getByText(wrapper, 'Claude Code、Codex CLI')).toBeTruthy()
  })

  it('shows the empty state and a create entry', async () => {
    installFetch((path) =>
      jsonResponse(
        path === '/api/profiles' ? profilesBody([]) : { tools: [], warnings: [] },
      ),
    )

    const wrapper = mountProfiles()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有档案')
    expect(getByRole(wrapper, 'button', { name: '新建档案' })).toBeTruthy()
  })

  it('shows a readable error and retries the list request', async () => {
    let failing = true
    installFetch((path) => {
      if (failing) {
        return Promise.reject(new TypeError('Failed to fetch'))
      }
      return jsonResponse(
        path === '/api/profiles' ? profilesBody([]) : { tools: [], warnings: [] },
      )
    })

    const wrapper = mountProfiles()
    await flushPromises()
    expect(getByRole(wrapper, 'alert').text()).toContain('无法连接后端服务')

    failing = false
    await getByRole(wrapper, 'button', { name: '重试' }).trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('还没有档案')
  })

  it('keeps old profiles and warns when a refresh fails', async () => {
    const profile = makeProfile()
    let failing = false
    installFetch((path) => {
      if (failing) {
        return Promise.reject(new TypeError('Failed to fetch'))
      }
      return jsonResponse(
        path === '/api/profiles' ? profilesBody([profile]) : { tools: [], warnings: [] },
      )
    })
    const wrapper = mountProfiles()
    await flushPromises()

    failing = true
    await getByRole(wrapper, 'button', { name: '刷新' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'heading', { name: 'Anthropic 主力' })).toBeTruthy()
    expect(wrapper.text()).toContain('刷新失败，当前显示上次结果')
  })

  it('creates a profile with models and a secret', async () => {
    const created = makeProfile({
      id: '22222222-2222-4222-8222-222222222222',
      name: '新档案',
      has_secret: true,
      secret_preview: 'sk-t****test',
      models: [{ id: 'gpt-5', display_name: null }],
    })
    let list: ProfileView[] = []
    installFetch((path, method, _body) => {
      if (path === '/api/tools') {
        return jsonResponse({ tools: [], warnings: [] })
      }
      if (path === '/api/profiles' && method === 'GET') {
        return jsonResponse(profilesBody(list))
      }
      if (path === '/api/profiles' && method === 'POST') {
        list = [created]
        return jsonResponse(created, 201)
      }
      return Promise.reject(new TypeError(`unexpected request: ${method} ${path}`))
    })
    const wrapper = mountProfiles()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '新建档案' }).trigger('click')
    await getByRole(wrapper, 'textbox', { name: '名称' }).setValue('新档案')
    await getByRole(wrapper, 'combobox', { name: '协议' }).setValue('openai')
    await getByRole(wrapper, 'textbox', { name: '接口地址' }).setValue(
      'https://api.openai.com/v1',
    )
    await getByRole(wrapper, 'button', { name: '添加模型' }).trigger('click')
    await getByRole(wrapper, 'textbox', { name: '模型标识' }).setValue('gpt-5')
    await getByRole(wrapper, 'textbox', { name: 'API 密钥' }).setValue('sk-test')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const posts = requestCalls('POST', '/api/profiles')
    expect(posts).toHaveLength(1)
    expect(posts[0]?.body).toEqual({
      name: '新档案',
      protocol: 'openai',
      base_url: 'https://api.openai.com/v1',
      models: [{ id: 'gpt-5', display_name: null }],
      secret: 'sk-test',
    })
    expect(wrapper.text()).toContain('已创建档案：新档案')
    expect(getByRole(wrapper, 'heading', { name: '新档案' })).toBeTruthy()
  })

  it('keeps the existing secret when the edit form leaves it blank', async () => {
    const profile = makeProfile()
    let current = profile
    installFetch((path, method) => {
      if (path === '/api/tools') {
        return jsonResponse({ tools: [], warnings: [] })
      }
      if (method === 'PATCH') {
        current = { ...profile, name: '改过的名字' }
        return jsonResponse(current)
      }
      return jsonResponse(profilesBody([current]))
    })
    const wrapper = mountProfiles()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '编辑档案 Anthropic 主力' }).trigger('click')
    await getByRole(wrapper, 'textbox', { name: '名称' }).setValue('改过的名字')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const patches = calls.filter((call) => call.method === 'PATCH')
    expect(patches).toHaveLength(1)
    const body = patches[0]?.body as Record<string, unknown>
    expect(body).not.toHaveProperty('secret')
    expect(body.name).toBe('改过的名字')
    expect(wrapper.text()).toContain('已保存档案：改过的名字')
  })

  it('clears the stored secret only when the explicit checkbox is used', async () => {
    const profile = makeProfile()
    const cleared = { ...profile, has_secret: false, secret_preview: null, secret_backend: null }
    let patched = false
    installFetch((path, method) => {
      if (path === '/api/tools') {
        return jsonResponse({ tools: [], warnings: [] })
      }
      if (method === 'PATCH') {
        patched = true
        return jsonResponse(cleared)
      }
      return jsonResponse(profilesBody([patched ? cleared : profile]))
    })
    const wrapper = mountProfiles()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '编辑档案 Anthropic 主力' }).trigger('click')
    const secretInput = getByRole(wrapper, 'textbox', { name: 'API 密钥' })
    expect(secretInput.attributes('type')).toBe('password')
    await getByRole(wrapper, 'checkbox', { name: '清除已保存的密钥' }).setValue(true)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const patch = calls.find((call) => call.method === 'PATCH')
    const patchBody = patch?.body as Record<string, unknown> | undefined
    expect(patchBody?.secret).toBeNull()
    expect(wrapper.text()).not.toContain('sk-a****cdef')
  })

  it('shows duplicate model hints and can add and remove model rows', async () => {
    installFetch((path) =>
      jsonResponse(
        path === '/api/profiles' ? profilesBody([]) : { tools: [], warnings: [] },
      ),
    )
    const wrapper = mountProfiles()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '新建档案' }).trigger('click')
    expect(wrapper.text()).toContain('尚未添加模型')
    await getByRole(wrapper, 'button', { name: '添加模型' }).trigger('click')
    expect(wrapper.text()).not.toContain('尚未添加模型')
    const idInputs = getAllByRole(wrapper, 'textbox', { name: '模型标识' })
    await idInputs[0]?.setValue('same')
    await getByRole(wrapper, 'button', { name: '添加模型' }).trigger('click')
    const secondInputs = getAllByRole(wrapper, 'textbox', { name: '模型标识' })
    await secondInputs[1]?.setValue('same')
    expect(wrapper.text()).toContain('模型清单存在重复项：same')

    const removeButtons = getAllByRole(wrapper, 'button', { name: '删除模型 same' })
    await removeButtons[0]?.trigger('click')
    await getByRole(wrapper, 'button', { name: '删除模型 same' }).trigger('click')
    expect(wrapper.text()).toContain('尚未添加模型')
  })

  it('copies a profile and reports the new name', async () => {
    const profile = makeProfile()
    const copied = makeProfile({
      id: '33333333-3333-4333-8333-333333333333',
      name: 'Anthropic 主力 (副本)',
    })
    let list = [profile]
    installFetch((path, method) => {
      if (path === '/api/tools') {
        return jsonResponse({ tools: [], warnings: [] })
      }
      if (method === 'POST' && path.endsWith('/copy')) {
        list = [profile, copied]
        return jsonResponse(copied, 201)
      }
      return jsonResponse(profilesBody(list))
    })
    const wrapper = mountProfiles()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '复制档案 Anthropic 主力' }).trigger('click')
    await flushPromises()

    expect(requestCalls('POST', `/api/profiles/${profile.id}/copy`)).toHaveLength(1)
    expect(wrapper.text()).toContain('已复制档案：Anthropic 主力 (副本)')
    expect(
      getByRole(wrapper, 'heading', { name: 'Anthropic 主力 (副本)' }),
    ).toBeTruthy()
  })

  it('cancels or confirms deletion and lists the tools using the profile', async () => {
    const profile = makeProfile({
      used_by: [
        { tool_id: 'claude-code', display_name: 'Claude Code', installed: true },
        { tool_id: 'codex-cli', display_name: 'Codex CLI', installed: true },
      ],
    })
    let list = [profile]
    installFetch((path, method) => {
      if (path === '/api/tools') {
        return jsonResponse({ tools: [], warnings: [] })
      }
      if (method === 'DELETE') {
        list = []
        return jsonResponse({
          deleted: true,
          unbound_tools: profile.used_by,
        })
      }
      return jsonResponse(profilesBody(list))
    })
    const wrapper = mountProfiles()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '删除档案 Anthropic 主力' }).trigger('click')
    const dialog = getByRole(wrapper, 'dialog')
    expect(dialog.text()).toContain('Claude Code')
    expect(dialog.text()).toContain('Codex CLI')

    await getByRole(dialog, 'button', { name: '取消' }).trigger('click')
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)

    await getByRole(wrapper, 'button', { name: '删除档案 Anthropic 主力' }).trigger('click')
    await getByRole(wrapper, 'dialog').trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)

    await getByRole(wrapper, 'button', { name: '删除档案 Anthropic 主力' }).trigger('click')
    await getByRole(wrapper, 'button', { name: '确认删除' }).trigger('click')
    await flushPromises()

    expect(requestCalls('DELETE', `/api/profiles/${profile.id}?confirm=true`)).toHaveLength(1)
    expect(wrapper.text()).toContain('已删除档案：Anthropic 主力')
    expect(wrapper.text()).toContain('还没有档案')
  })

  it('binds and unbinds a tool with a not-applied label', async () => {
    const profile = makeProfile()
    const tool = makeTool()
    let bindings: BindingView[] = []
    installFetch((path, method, _body) => {
      if (path === '/api/tools') {
        return jsonResponse({ tools: [tool], warnings: [] })
      }
      if (method === 'PUT') {
        bindings = [makeBinding(profile.id, 'claude-code')]
        return jsonResponse(bindings[0])
      }
      if (method === 'DELETE') {
        bindings = []
        return jsonResponse({ tool_id: 'claude-code', removed: true })
      }
      return jsonResponse(profilesBody([profile], bindings))
    })
    const wrapper = mountProfiles()
    await flushPromises()

    await getByRole(wrapper, 'combobox', { name: '为 Claude Code 选择档案' }).setValue(
      profile.id,
    )
    await getByRole(wrapper, 'button', { name: '绑定 Claude Code' }).trigger('click')
    await flushPromises()

    const put = requestCalls('PUT', '/api/tools/claude-code/profile')
    expect(put).toHaveLength(1)
    expect(put[0]?.body).toEqual({ profile_id: profile.id })
    expect(wrapper.text()).toContain('已绑定，尚未应用')
    expect(wrapper.text()).toContain('在主界面详情中应用后生效')

    await getByRole(wrapper, 'button', { name: '解除 Claude Code 的绑定' }).trigger('click')
    await flushPromises()

    expect(requestCalls('DELETE', '/api/tools/claude-code/profile')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('已绑定，尚未应用')
    expect(wrapper.text()).toContain('已解除绑定；工具里已生效的配置不会被回滚')
  })

  it('shows applied bindings with snapshot details and flags later profile edits', async () => {
    const profile = makeProfile({ updated_at: '2026-11-11T12:00:00Z' })
    installFetch((path) =>
      jsonResponse(
        path === '/api/profiles'
          ? profilesBody([profile], [makeAppliedBinding(profile.id)])
          : { tools: [makeTool()], warnings: [] },
      ),
    )
    const wrapper = mountProfiles()
    await flushPromises()

    expect(wrapper.text()).toContain('已应用')
    expect(wrapper.text()).toContain(`快照 ${appliedSnapshotId}`)
    expect(wrapper.text()).toContain('档案已修改，需重新应用')
    expect(wrapper.text()).not.toContain('已绑定，尚未应用')
  })

  it('does not flag a binding applied after the profile was last edited', async () => {
    const profile = makeProfile({ updated_at: '2026-11-10T12:00:00Z' })
    installFetch((path) =>
      jsonResponse(
        path === '/api/profiles'
          ? profilesBody([profile], [makeAppliedBinding(profile.id)])
          : { tools: [makeTool()], warnings: [] },
      ),
    )
    const wrapper = mountProfiles()
    await flushPromises()

    expect(wrapper.text()).toContain('已应用')
    expect(wrapper.text()).toContain(`快照 ${appliedSnapshotId}`)
    expect(wrapper.text()).not.toContain('档案已修改，需重新应用')
  })

  it('lists uninstalled tools that still have bindings', async () => {
    const profile = makeProfile()
    installFetch((path) =>
      jsonResponse(
        path === '/api/profiles'
          ? profilesBody([profile], [makeBinding(profile.id, 'removed-tool')])
          : { tools: [], warnings: [] },
      ),
    )
    const wrapper = mountProfiles()
    await flushPromises()

    expect(wrapper.text()).toContain('已卸载但仍有绑定')
    expect(wrapper.text()).toContain('removed-tool')
    expect(wrapper.text()).toContain('已不可用')
  })

  it('shows the file fallback banner', async () => {
    installFetch((path) =>
      jsonResponse(
        path === '/api/profiles'
          ? profilesBody([], [], {
              backend: 'file',
              fallback: true,
              message: '系统钥匙串不可用, 密钥将保存在本机文件 secrets.json (权限 0600)',
            })
          : { tools: [], warnings: [] },
      ),
    )
    const wrapper = mountProfiles()
    await flushPromises()

    expect(wrapper.text()).toContain('系统钥匙串不可用，密钥保存在本机文件')
    expect(wrapper.text()).toContain('secrets.json')
  })

  it('shows an error banner when no secret backend is available', async () => {
    installFetch((path) =>
      jsonResponse(
        path === '/api/profiles'
          ? profilesBody([], [], {
              backend: 'unavailable',
              fallback: false,
              message: '系统钥匙串与本机密钥文件均不可用, 无法保存密钥',
            })
          : { tools: [], warnings: [] },
      ),
    )
    const wrapper = mountProfiles()
    await flushPromises()

    const alerts = getAllByRole(wrapper, 'alert')
    expect(alerts.some((alert) => alert.text().includes('密钥存储不可用'))).toBe(true)
  })

  it('shows secret warnings instead of pretending no secret is set', async () => {
    const profile = makeProfile({
      has_secret: false,
      secret_preview: null,
      secret_backend: 'keyring',
      warnings: [
        {
          code: 'SECRET_MISSING',
          message: '密钥引用存在, 但密钥存储中没有对应条目',
        },
      ],
    })
    installFetch((path) =>
      jsonResponse(
        path === '/api/profiles'
          ? profilesBody([profile])
          : { tools: [], warnings: [] },
      ),
    )
    const wrapper = mountProfiles()
    await flushPromises()

    expect(wrapper.text()).toContain('密钥缺失')
    expect(wrapper.text()).toContain('密钥引用存在')
    expect(wrapper.text()).not.toContain('未设置密钥')
  })

  it('lets a user choose a model and view an explicit health result', async () => {
    const profile = makeProfile()
    installFetch((path, method) => {
      if (path === '/api/tools') {
        return jsonResponse({ tools: [], warnings: [] })
      }
      if (path === '/api/profiles') {
        return jsonResponse(profilesBody([profile]))
      }
      if (method === 'POST' && path.endsWith('/health-check')) {
        return jsonResponse({
          profile_id: profile.id,
          model: 'claude-sonnet-4',
          status: 'CONNECTED',
          attempted: true,
          duration_ms: 87,
          message: '连接成功。档案地址、凭证和模型可用',
          checked_at: '2026-11-12T10:00:00Z',
        })
      }
      return Promise.reject(new TypeError(`unexpected request: ${method} ${path}`))
    })
    const wrapper = mountProfiles()
    await flushPromises()

    const model = getByRole(wrapper, 'combobox', { name: '体检模型' })
    expect((model.element as HTMLSelectElement).value).toBe('claude-sonnet-4')
    expect(
      getByRole(wrapper, 'button', { name: '体检档案 Anthropic 主力' }).element.tagName,
    ).toBe('BUTTON')
    expect(wrapper.text()).toContain('可能产生少量费用')
    expect(wrapper.text()).toContain('不会发送聊天内容')

    await getByRole(wrapper, 'button', { name: '体检档案 Anthropic 主力' }).trigger('click')
    await flushPromises()

    const healthChecks = requestCalls('POST', `/api/profiles/${profile.id}/health-check`)
    expect(healthChecks).toHaveLength(1)
    expect(healthChecks[0]?.body).toEqual({ model: 'claude-sonnet-4' })
    expect(getByRole(wrapper, 'status').text()).toContain('耗时 87 ms')
    expect(wrapper.text()).toContain('连接成功。档案地址、凭证和模型可用')
  })

  it('disables model-less health checks and explains how to enable them', async () => {
    const profile = makeProfile({ models: [] })
    installFetch((path) =>
      jsonResponse(
        path === '/api/profiles' ? profilesBody([profile]) : { tools: [], warnings: [] },
      ),
    )
    const wrapper = mountProfiles()
    await flushPromises()

    expect(wrapper.text()).toContain('尚无模型')
    expect(
      getByRole(wrapper, 'button', { name: '体检档案 Anthropic 主力' }).attributes('disabled'),
    ).toBeDefined()
    expect(calls.some((call) => call.path.endsWith('/health-check'))).toBe(false)
  })

  it('prevents duplicate health requests while one is pending', async () => {
    const profile = makeProfile()
    const healthRequest: { resolve?: (response: Response) => void } = {}
    installFetch((path, method) => {
      if (path === '/api/tools') {
        return jsonResponse({ tools: [], warnings: [] })
      }
      if (method === 'POST' && path.endsWith('/health-check')) {
        return new Promise<Response>((resolve) => {
          healthRequest.resolve = resolve
        })
      }
      return jsonResponse(profilesBody([profile]))
    })
    const wrapper = mountProfiles()
    await flushPromises()

    const button = getByRole(wrapper, 'button', { name: '体检档案 Anthropic 主力' })
    await button.trigger('click')
    await flushPromises()
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')
    expect(requestCalls('POST', `/api/profiles/${profile.id}/health-check`)).toHaveLength(1)

    healthRequest.resolve?.(
      jsonResponse({
        profile_id: profile.id,
        model: 'claude-sonnet-4',
        status: 'CONNECTED',
        attempted: true,
        duration_ms: 5,
        message: '连接成功',
        checked_at: '2026-11-12T10:00:00Z',
      }),
    )
    await flushPromises()
    expect(button.attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('连接成功')
  })

  it('shows request errors and allows a health check retry', async () => {
    const profile = makeProfile()
    let fail = true
    installFetch((path, method) => {
      if (path === '/api/tools') {
        return jsonResponse({ tools: [], warnings: [] })
      }
      if (method === 'POST' && path.endsWith('/health-check')) {
        if (fail) {
          return jsonResponse({ code: 'INTERNAL_ERROR', message: '体检服务暂不可用' }, 500)
        }
        return jsonResponse({
          profile_id: profile.id,
          model: 'claude-sonnet-4',
          status: 'CONNECTED',
          attempted: true,
          duration_ms: 5,
          message: '连接成功',
          checked_at: '2026-11-12T10:00:00Z',
        })
      }
      return jsonResponse(profilesBody([profile]))
    })
    const wrapper = mountProfiles()
    await flushPromises()
    const button = getByRole(wrapper, 'button', { name: '体检档案 Anthropic 主力' })

    await button.trigger('click')
    await flushPromises()
    expect(getByRole(wrapper, 'alert').text()).toContain('体检服务暂不可用')

    fail = false
    await button.trigger('click')
    await flushPromises()
    expect(requestCalls('POST', `/api/profiles/${profile.id}/health-check`)).toHaveLength(2)
    expect(wrapper.text()).toContain('连接成功')
  })
})