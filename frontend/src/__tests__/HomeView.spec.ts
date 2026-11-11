import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { ProfileListResponse, ProfileView } from '../api/profiles'
import type { SwitchApplyResponse, SwitchPreviewResponse } from '../api/switch'
import type { ToolView } from '../api/tools'
import HomeView from '../views/HomeView.vue'
import { getAllByRole, getByRole, getByText } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

const capabilities: ToolView['capabilities'] = {
  read: true,
  write: false,
  sessions: false,
  launch: false,
  write_mode: 'none',
}

function makeTool(overrides: Partial<ToolView>): ToolView {
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
    last_modified: '2023-11-14T22:13:20+00:00',
    has_secret: true,
    secret_preview: 'sk-a****cdef',
    warnings: [],
    capabilities,
    ...overrides,
  }
}

const claudeTool = makeTool({})

const codexTool = makeTool({
  id: 'codex-cli',
  display_name: 'Codex CLI',
  status: 'unconfigured',
  configured: false,
  provider: null,
  base_url: null,
  model: null,
  is_third_party: null,
  config_path: '/home/me/.codex/config.toml',
  has_secret: false,
  secret_preview: null,
})

const emptyProfiles: ProfileListResponse = {
  profiles: [],
  bindings: [],
  secret_store: { backend: 'keyring', fallback: false, message: null },
  warnings: [],
}

const emptySnapshots = { snapshots: [], retention_limit: 20, warnings: [] }

function stubApi(routes: Record<string, unknown>) {
  const mock = vi.fn<(path: string) => Promise<Response>>((path) => {
    const body = routes[path]
    if (body !== undefined) {
      return Promise.resolve(jsonResponse(body))
    }
    if (path === '/api/profiles') {
      return Promise.resolve(jsonResponse(emptyProfiles))
    }
    if (path.startsWith('/api/snapshots')) {
      return Promise.resolve(jsonResponse(emptySnapshots))
    }
    return Promise.reject(new TypeError(`unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

const relayProfile: ProfileView = {
  id: 'profile-1',
  name: '主力档案',
  protocol: 'anthropic',
  base_url: 'https://relay.example.com',
  models: [{ id: 'claude-sonnet-4', display_name: 'Sonnet' }],
  created_at: '2026-11-10T12:00:00Z',
  updated_at: '2026-11-10T12:00:00Z',
  has_secret: true,
  secret_preview: 'sk-a****cdef',
  secret_backend: 'keyring',
  used_by: [],
  warnings: [],
}

const profilesWithRelay: ProfileListResponse = {
  profiles: [relayProfile],
  bindings: [],
  secret_store: { backend: 'keyring', fallback: false, message: null },
  warnings: [],
}

function makePreview(): SwitchPreviewResponse {
  return {
    tool_id: 'claude-code',
    profile_id: relayProfile.id,
    model: 'claude-sonnet-4',
    available_models: relayProfile.models,
    files: [
      {
        path: '/home/me/.claude/settings.json',
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
            before: 'https://api.anthropic.com',
            after: relayProfile.base_url,
          },
        ],
      },
    ],
    blockers: [],
    warnings: [],
    restart_required: true,
    restart_message: 'Claude Code 需要重启后才会读取新的 settings.json',
    observations: [
      {
        path: '/home/me/.claude/settings.json',
        exists: true,
        sha256: 'a'.repeat(64),
        size: 120,
        mtime_ns: 1,
      },
    ],
    preview_digest: 'c'.repeat(64),
    can_apply: true,
  }
}

function makeApply(): SwitchApplyResponse {
  return {
    tool_id: 'claude-code',
    profile_id: relayProfile.id,
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
      tool_id: 'claude-code',
      profile_id: relayProfile.id,
      bound_at: '2026-11-11T12:00:00Z',
      active: true,
      applied_at: '2026-11-11T12:00:00Z',
      snapshot_id: '11111111-1111-4111-8111-111111111111',
    },
    warnings: [],
    restart_required: true,
    restart_message: 'Claude Code 需要重启后才会读取新的 settings.json',
    applied_at: '2026-11-11T12:00:00Z',
  }
}

function mountHome() {
  return mount(HomeView, { global: { plugins: [createPinia()] } })
}

describe('HomeView', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a 检测中 badge while the tool list is pending', async () => {
    let resolveList: ((response: Response) => void) | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string) => {
        if (path === '/api/profiles') {
          return Promise.resolve(jsonResponse(emptyProfiles))
        }
        return new Promise<Response>((resolve) => {
          resolveList = resolve
        })
      }),
    )
    const wrapper = mountHome()
    await flushPromises()

    expect(getByText(wrapper, '检测中')).toBeTruthy()
    expect(getByText(wrapper, '正在检测…')).toBeTruthy()
    expect(wrapper.text()).not.toContain('选择一个 AI 查看详情')
    expect(wrapper.text()).not.toContain('还没有发现任何 AI 工具')

    resolveList?.(jsonResponse({ tools: [claudeTool], warnings: [] }))
    await flushPromises()

    expect(getByRole(wrapper, 'button', { name: 'Claude Code' })).toBeTruthy()
  })

  it('sorts friends by last_modified descending and puts unknown times last', async () => {
    stubApi({
      '/api/tools': {
        tools: [
          makeTool({ id: 'charlie', display_name: 'Charlie', last_modified: null }),
          makeTool({
            id: 'bravo',
            display_name: 'Bravo',
            last_modified: '2024-01-01T00:00:00+00:00',
          }),
          makeTool({ id: 'delta', display_name: 'Delta', last_modified: 'not-a-date' }),
          makeTool({ id: 'echo', display_name: 'Echo', last_modified: '2023-01-01T00:00:00+00:00' }),
          makeTool({
            id: 'alpha',
            display_name: 'Alpha',
            last_modified: '2024-01-01T00:00:00+00:00',
          }),
        ],
        warnings: [],
      },
    })
    const wrapper = mountHome()
    await flushPromises()

    const labels = getAllByRole(wrapper, 'button')
      .map((button) => button.attributes('aria-label'))
      .filter((label): label is string => label !== undefined)

    expect(labels).toEqual(['选择 Alpha', '选择 Bravo', '选择 Echo', '选择 Charlie', '选择 Delta'])
    expect(getByText(wrapper, 'A')).toBeTruthy()
  })

  it('renders the four status states with a readable one-line description', async () => {
    stubApi({
      '/api/tools': {
        tools: [
          claudeTool,
          codexTool,
          makeTool({
            id: 'broken-tool',
            display_name: 'Broken Tool',
            status: 'error',
            warnings: [{ code: 'PARSE_ERROR', message: 'settings.json 格式错误' }],
          }),
        ],
        warnings: [],
      },
    })
    const wrapper = mountHome()
    await flushPromises()

    expect(getByRole(wrapper, 'button', { name: 'Claude Code' }).text()).toContain('正常')
    expect(getByText(wrapper, 'Anthropic / claude-sonnet-4')).toBeTruthy()
    expect(getByRole(wrapper, 'button', { name: 'Codex CLI' }).text()).toContain('未配置')
    expect(getByText(wrapper, '已安装，尚未配置')).toBeTruthy()
    expect(getByRole(wrapper, 'button', { name: 'Broken Tool' }).text()).toContain('异常')
    expect(getByText(wrapper, 'settings.json 格式错误')).toBeTruthy()
  })

  it('shows the selected friend detail and keeps the selection on refresh', async () => {
    stubApi({
      '/api/tools': { tools: [claudeTool, codexTool], warnings: [] },
      '/api/tools/claude-code': {
        ...claudeTool,
        base_url: 'https://relay.example.com',
        is_third_party: true,
        warnings: [
          { code: 'SECRET_IN_ENV', message: '密钥来自环境变量 MY_TEST_KEY, 本应用不读取' },
        ],
      },
    })
    const wrapper = mountHome()
    await flushPromises()

    expect(getByText(wrapper, '选择一个 AI 查看详情')).toBeTruthy()
    expect(getByRole(wrapper, 'list').attributes('aria-label')).toBe('AI 好友列表')

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'button', { name: 'Claude Code' }).attributes('aria-pressed')).toBe(
      'true',
    )
    expect(getByRole(wrapper, 'button', { name: 'Claude Code' }).attributes('aria-label')).toBe(
      '选择 Claude Code',
    )
    expect(getByRole(wrapper, 'heading', { name: 'Claude Code' })).toBeTruthy()
    expect(getByText(wrapper, 'https://relay.example.com')).toBeTruthy()
    expect(getByText(wrapper, '是')).toBeTruthy()
    expect(getByText(wrapper, 'sk-a****cdef')).toBeTruthy()
    expect(getByText(wrapper, '/home/me/.claude/settings.json')).toBeTruthy()
    expect(
      getByText(wrapper, 'SECRET_IN_ENV: 密钥来自环境变量 MY_TEST_KEY, 本应用不读取'),
    ).toBeTruthy()

    stubApi({ '/api/tools': { tools: [claudeTool, codexTool], warnings: [] } })
    await getByRole(wrapper, 'button', { name: '刷新' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'button', { name: 'Claude Code' }).attributes('aria-pressed')).toBe(
      'true',
    )
    expect(getByRole(wrapper, 'heading', { name: 'Claude Code' })).toBeTruthy()
  })

  it('clears the selection when the selected friend disappears after refresh', async () => {
    stubApi({
      '/api/tools': { tools: [claudeTool, codexTool], warnings: [] },
      '/api/tools/claude-code': claudeTool,
    })
    const wrapper = mountHome()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    stubApi({ '/api/tools': { tools: [codexTool], warnings: [] } })
    await getByRole(wrapper, 'button', { name: '刷新' }).trigger('click')
    await flushPromises()

    expect(getByText(wrapper, '选择一个 AI 查看详情')).toBeTruthy()
    expect(wrapper.text()).not.toContain('Claude Code')
  })

  it('shows the global empty state and expands the install guide without requests', async () => {
    const fetchMock = stubApi({ '/api/tools': { tools: [], warnings: [] } })
    const wrapper = mountHome()
    await flushPromises()

    expect(getByRole(wrapper, 'heading', { name: '还没有发现任何 AI 工具' })).toBeTruthy()
    const toggle = getByRole(wrapper, 'button', { name: '怎么装' })
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.text()).not.toContain('npm install -g @anthropic-ai/claude-code')
    const callsAfterLoad = fetchMock.mock.calls.length
    expect(callsAfterLoad).toBe(2)

    await toggle.trigger('click')

    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(getByText(wrapper, 'npm install -g @anthropic-ai/claude-code')).toBeTruthy()
    expect(getByText(wrapper, 'npm install -g @openai/codex')).toBeTruthy()
    expect(getByText(wrapper, 'Claude Code')).toBeTruthy()
    expect(getByText(wrapper, 'Codex CLI')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(callsAfterLoad)
  })

  it('shows partial-failure warnings behind a discoverable toggle', async () => {
    stubApi({
      '/api/tools': {
        tools: [
          claudeTool,
          makeTool({
            id: 'broken-tool',
            display_name: 'Broken Tool',
            status: 'error',
            warnings: [{ code: 'PARSE_ERROR', message: 'settings.json 格式错误' }],
          }),
        ],
        warnings: [{ code: 'ADAPTER_ERROR', message: '适配器 broken-tool 读取失败: RuntimeError' }],
      },
    })
    const wrapper = mountHome()
    await flushPromises()

    expect(getByRole(wrapper, 'button', { name: 'Claude Code' })).toBeTruthy()
    expect(getByRole(wrapper, 'button', { name: 'Broken Tool' }).text()).toContain('异常')

    const toggle = getByRole(wrapper, 'button', { name: '部分工具检测失败（1）' })
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.text()).not.toContain('适配器 broken-tool 读取失败: RuntimeError')

    await toggle.trigger('click')

    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(getByText(wrapper, '适配器 broken-tool 读取失败: RuntimeError')).toBeTruthy()
  })

  it('shows a readable error with retry after the initial request fails, then recovers', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const wrapper = mountHome()
    await flushPromises()

    expect(getByRole(wrapper, 'alert').text()).toContain('无法连接后端服务')
    expect(getByText(wrapper, '工具列表加载失败，请重试')).toBeTruthy()

    stubApi({ '/api/tools': { tools: [claudeTool], warnings: [] } })
    await getByRole(wrapper, 'button', { name: '重试' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'button', { name: 'Claude Code' })).toBeTruthy()
    expect(wrapper.text()).not.toContain('无法连接后端服务')
  })

  it('keeps the old list and shows a non-blocking notice when a refresh fails', async () => {
    stubApi({ '/api/tools': { tools: [claudeTool], warnings: [] } })
    const wrapper = mountHome()
    await flushPromises()

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await getByRole(wrapper, 'button', { name: '刷新' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'button', { name: 'Claude Code' })).toBeTruthy()
    expect(getByText(wrapper, '刷新失败，当前显示上次结果：无法连接后端服务')).toBeTruthy()
    expect(wrapper.text()).not.toContain('重试')
  })

  it('shows the switch and snapshot sections and refreshes them after an apply', async () => {
    const fetchMock = stubApi({
      '/api/tools': { tools: [claudeTool], warnings: [] },
      '/api/tools/claude-code': claudeTool,
      '/api/profiles': profilesWithRelay,
      '/api/switch/preview': makePreview(),
      '/api/switch/apply': makeApply(),
    })
    const wrapper = mountHome()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'heading', { name: '切换档案' })).toBeTruthy()
    expect(
      getByRole(wrapper, 'combobox', { name: '选择档案' }).element,
    ).toHaveProperty('value', relayProfile.id)
    expect(getByRole(wrapper, 'heading', { name: '快照 / 回滚' })).toBeTruthy()
    expect(getByText(wrapper, '暂无快照，应用档案后会自动生成')).toBeTruthy()

    await getByRole(wrapper, 'button', { name: '预览改动' }).trigger('click')
    await flushPromises()
    await getByRole(wrapper, 'button', { name: '确认应用' }).trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已应用档案配置')
    const snapshotCalls = fetchMock.mock.calls.filter(([path]) =>
      String(path).startsWith('/api/snapshots'),
    )
    expect(snapshotCalls).toHaveLength(2)
  })
})