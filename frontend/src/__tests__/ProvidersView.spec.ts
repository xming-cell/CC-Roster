import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { DOMWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { BindingView, HealthCheckResponse, ProfileListResponse, ProfileView } from '../api/profiles'
import type { ToolView } from '../api/tools'
import ProvidersView from '../views/ProvidersView.vue'
import { getByRole, getByText } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

function parseBody(init?: RequestInit): Record<string, unknown> {
  if (typeof init?.body !== 'string') {
    return {}
  }
  return JSON.parse(init.body) as Record<string, unknown>
}

const NOW = '2026-11-17T10:00:00+00:00'
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
    model: 'claude-sonnet-4-5',
    is_third_party: false,
    config_path: '/home/me/.claude/settings.json',
    last_modified: NOW,
    has_secret: true,
    secret_preview: 'sk-a...cdef',
    warnings: [],
    capabilities,
    ...overrides,
  }
}

function makeProfile(overrides: Partial<ProfileView> & { id: string; name: string }): ProfileView {
  return {
    protocol: 'anthropic',
    base_url: 'https://api.anthropic.com',
    models: [{ id: 'claude-sonnet-4-5', display_name: null }],
    created_at: NOW,
    updated_at: NOW,
    has_secret: true,
    secret_preview: 'sk-a...cdef',
    secret_backend: 'keyring',
    used_by: [],
    warnings: [],
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
  has_secret: false,
  secret_preview: null,
})
const brokenTool = makeTool({
  id: 'broken-tool',
  display_name: 'Broken Tool',
  status: 'error',
  configured: false,
  warnings: [{ code: 'PARSE_ERROR', message: '配置格式错误' }],
})

const profileA = makeProfile({ id: 'profile-a', name: 'Anthropic 官方' })
const profileB = makeProfile({
  id: 'profile-b',
  name: 'Kimi K2',
  protocol: 'openai',
  base_url: 'https://api.moonshot.cn/v1',
  models: [{ id: 'kimi-k2-0905-preview', display_name: null }],
  has_secret: true,
  secret_preview: 'sk-m...71c8',
})
const profileC = makeProfile({
  id: 'profile-c',
  name: 'Codex 供应商',
  protocol: 'openai',
  base_url: 'https://api.example.com/v1',
  models: [{ id: 'gpt-5', display_name: null }],
})

const bindingA: BindingView = {
  tool_id: 'claude-code',
  profile_id: 'profile-a',
  bound_at: NOW,
  active: true,
  applied_at: null,
  snapshot_id: null,
}
const bindingB: BindingView = {
  tool_id: 'claude-code',
  profile_id: 'profile-b',
  bound_at: NOW,
  active: false,
  applied_at: null,
  snapshot_id: null,
}
const bindingRemoved: BindingView = {
  tool_id: 'removed-tool',
  profile_id: 'profile-a',
  bound_at: NOW,
  active: false,
  applied_at: null,
  snapshot_id: null,
}
const bindingC: BindingView = {
  tool_id: 'codex-cli',
  profile_id: 'profile-c',
  bound_at: NOW,
  active: false,
  applied_at: null,
  snapshot_id: null,
}

const defaultHealth: HealthCheckResponse = {
  profile_id: 'profile-a',
  model: 'claude-sonnet-4-5',
  status: 'CONNECTED',
  attempted: true,
  duration_ms: 428,
  message: '连接正常',
  checked_at: NOW,
}

interface CallRecord {
  path: string
  method: string
  body: Record<string, unknown>
}

interface DeferredResponse {
  resolve: (response: Response) => void
}

class FakeServer {
  tools: ToolView[]
  profiles: ProfileView[]
  bindings: BindingView[]
  health: HealthCheckResponse
  calls: CallRecord[] = []
  listErrorTool: string | null = null
  toolsError = false
  failBind = false
  healthGate: Promise<void> | null = null
  private holds = new Map<string, { promise: Promise<Response>; resolve: (response: Response) => void }>()
  private createSeq = 0
  private copySeq = 0

  constructor(options: {
    tools?: ToolView[]
    profiles?: ProfileView[]
    bindings?: BindingView[]
    health?: HealthCheckResponse
  } = {}) {
    this.tools = (options.tools ?? [claudeTool, codexTool, brokenTool]).map((tool) => ({ ...tool }))
    this.profiles = (options.profiles ?? [profileA, profileB]).map((profile) => ({
      ...profile,
      models: profile.models.map((model) => ({ ...model })),
      used_by: profile.used_by.map((tool) => ({ ...tool })),
      warnings: profile.warnings.map((warning) => ({ ...warning })),
    }))
    this.bindings = (options.bindings ?? [bindingA, bindingB, bindingRemoved]).map((binding) => ({ ...binding }))
    this.health = options.health ?? { ...defaultHealth }
  }

  view(profile: ProfileView): ProfileView {
    return {
      ...profile,
      used_by: this.bindings
        .filter((binding) => binding.profile_id === profile.id)
        .map((binding) => {
          const tool = this.tools.find((item) => item.id === binding.tool_id)
          return {
            tool_id: binding.tool_id,
            display_name: tool?.display_name ?? binding.tool_id,
            installed: tool !== undefined,
          }
        }),
    }
  }

  listResponse(toolId: string | null): ProfileListResponse {
    const bindings = toolId === null
      ? this.bindings
      : this.bindings.filter((binding) => binding.tool_id === toolId)
    const profileIds = new Set(bindings.map((binding) => binding.profile_id))
    const profiles = (toolId === null ? this.profiles : this.profiles.filter((profile) => profileIds.has(profile.id)))
      .map((profile) => this.view(profile))
    return {
      profiles,
      bindings,
      secret_store: { backend: 'keyring', fallback: false, message: null },
      warnings: [],
    }
  }

  defer(toolId: string): DeferredResponse {
    let resolveFn: ((response: Response) => void) | undefined
    const promise = new Promise<Response>((resolve) => {
      resolveFn = resolve
    })
    this.holds.set(toolId, {
      promise,
      resolve: (response) => resolveFn?.(response),
    })
    return { resolve: (response) => resolveFn?.(response) }
  }

  deferHealth(): { resolve: () => void } {
    let resolveFn: (() => void) | undefined
    this.healthGate = new Promise<void>((resolve) => {
      resolveFn = resolve
    })
    return { resolve: () => resolveFn?.() }
  }

  handle = async (path: string, init?: RequestInit): Promise<Response> => {
    const method = init?.method ?? 'GET'
    const body = parseBody(init)
    this.calls.push({ path, method, body })
    const url = new URL(path, 'http://local')

    if (url.pathname === '/api/tools') {
      if (this.toolsError) {
        return jsonResponse({ code: 'INTERNAL_ERROR', message: '工具读取失败' }, 500)
      }
      return jsonResponse({ tools: this.tools, warnings: [] })
    }

    if (url.pathname === '/api/switch/preview' && method === 'POST') {
      const file = '/home/me/.claude/settings.json'
      return jsonResponse({
        tool_id: 'claude-code',
        profile_id: body.profile_id,
        model: 'claude-sonnet-4-5',
        available_models: [],
        files: [
          {
            path: file,
            format: 'json',
            action: 'updated',
            before_sha256: null,
            after_sha256: 'b'.repeat(64),
            before_size: 0,
            after_size: 10,
            changes: [
              { path: file, field: 'model', action: 'set', before: 'claude-opus-4', after: 'claude-sonnet-4' },
            ],
          },
        ],
        blockers: [],
        warnings: [],
        restart_required: false,
        restart_message: '',
        observations: [],
        preview_digest: 'c'.repeat(64),
        can_apply: true,
      })
    }

    if (url.pathname === '/api/profiles' && method === 'GET') {
      const toolId = url.searchParams.get('tool_id')
      if (toolId !== null && this.listErrorTool === toolId) {
        return jsonResponse({ code: 'INTERNAL_ERROR', message: '供应商列表读取失败' }, 500)
      }
      if (toolId !== null && this.holds.has(toolId)) {
        const held = this.holds.get(toolId)
        if (held !== undefined) {
          return held.promise
        }
      }
      return jsonResponse(this.listResponse(toolId))
    }

    if (url.pathname === '/api/profiles' && method === 'POST') {
      const payload = body as unknown as {
        name: string
        protocol: ProfileView['protocol']
        base_url: string
        models: ProfileView['models']
        secret: string | null
      }
      this.createSeq += 1
      const created = makeProfile({
        id: 'profile-created-' + this.createSeq,
        name: payload.name,
        protocol: payload.protocol,
        base_url: payload.base_url,
        models: payload.models,
        has_secret: payload.secret !== null,
        secret_preview: payload.secret === null ? null : 'sk-n...0001',
        secret_backend: payload.secret === null ? null : 'keyring',
      })
      this.profiles.push(created)
      return jsonResponse(this.view(created), 201)
    }

    const copyMatch = /^\/api\/profiles\/([^/]+)\/copy$/.exec(url.pathname)
    if (copyMatch !== null && method === 'POST') {
      const sourceId = copyMatch[1] ?? ''
      const source = this.profiles.find((profile) => profile.id === sourceId)
      if (source === undefined) {
        return jsonResponse({ code: 'PROFILE_NOT_FOUND', message: '供应商不存在' }, 404)
      }
      this.copySeq += 1
      const requestedName = typeof body.name === 'string' ? body.name : source.name + ' (副本)'
      const copied = makeProfile({
        ...source,
        id: 'profile-copy-' + this.copySeq,
        name: requestedName,
        created_at: NOW,
        updated_at: NOW,
      })
      this.profiles.push(copied)
      return jsonResponse(this.view(copied), 201)
    }

    const profileMatch = /^\/api\/profiles\/([^/]+)$/.exec(url.pathname)
    if (profileMatch !== null && method === 'PATCH') {
      const profile = this.profiles.find((item) => item.id === profileMatch[1])
      if (profile === undefined) {
        return jsonResponse({ code: 'PROFILE_NOT_FOUND', message: '供应商不存在' }, 404)
      }
      const payload = body as unknown as {
        name?: string
        protocol?: ProfileView['protocol']
        base_url?: string
        models?: ProfileView['models']
        secret?: string | null
      }
      if (payload.name !== undefined) profile.name = payload.name
      if (payload.protocol !== undefined) profile.protocol = payload.protocol
      if (payload.base_url !== undefined) profile.base_url = payload.base_url
      if (payload.models !== undefined) profile.models = payload.models
      if (payload.secret === null) {
        profile.has_secret = false
        profile.secret_preview = null
        profile.secret_backend = null
      } else if (typeof payload.secret === 'string') {
        profile.has_secret = true
        profile.secret_preview = 'sk-n...9999'
        profile.secret_backend = 'keyring'
      }
      profile.updated_at = NOW
      return jsonResponse(this.view(profile))
    }

    if (profileMatch !== null && method === 'DELETE') {
      const profileId = profileMatch[1] ?? ''
      const bound = this.bindings.filter((binding) => binding.profile_id === profileId)
      const confirm = url.searchParams.get('confirm') === 'true'
      if (bound.length > 0 && !confirm) {
        return jsonResponse({ code: 'PROFILE_IN_USE', message: '供应商仍被工具使用' }, 409)
      }
      this.bindings = this.bindings.filter((binding) => binding.profile_id !== profileId)
      this.profiles = this.profiles.filter((profile) => profile.id !== profileId)
      return jsonResponse({ deleted: true, unbound_tools: bound.map((binding) => ({ tool_id: binding.tool_id, display_name: binding.tool_id, installed: false })) })
    }

    const healthMatch = /^\/api\/profiles\/([^/]+)\/health-check$/.exec(url.pathname)
    if (healthMatch !== null && method === 'POST') {
      if (this.healthGate !== null) {
        await this.healthGate
      }
      return jsonResponse(this.health)
    }

    const bindMatch = /^\/api\/tools\/([^/]+)\/profile$/.exec(url.pathname)
    if (bindMatch !== null && method === 'PUT') {
      if (this.failBind) {
        return jsonResponse({ code: 'INTERNAL_ERROR', message: '绑定失败' }, 500)
      }
      const toolId = bindMatch[1] ?? ''
      const profileId = typeof body.profile_id === 'string' ? body.profile_id : ''
      const existing = this.bindings.find((binding) => binding.tool_id === toolId && binding.profile_id === profileId)
      if (existing !== undefined) {
        return jsonResponse(existing)
      }
      const binding: BindingView = {
        tool_id: toolId,
        profile_id: profileId,
        bound_at: NOW,
        active: false,
        applied_at: null,
        snapshot_id: null,
      }
      this.bindings.push(binding)
      return jsonResponse(binding)
    }

    const unbindMatch = /^\/api\/tools\/([^/]+)\/profiles\/([^/]+)$/.exec(url.pathname)
    if (unbindMatch !== null && method === 'DELETE') {
      const toolId = unbindMatch[1] ?? ''
      const profileId = unbindMatch[2] ?? ''
      const before = this.bindings.length
      this.bindings = this.bindings.filter((binding) => !(binding.tool_id === toolId && binding.profile_id === profileId))
      return jsonResponse({ tool_id: toolId, removed: this.bindings.length < before })
    }

    throw new Error('unexpected request: ' + method + ' ' + url.pathname)
  }
}

function mountProviders(server: FakeServer) {
  vi.stubGlobal('fetch', vi.fn((path: string, init?: RequestInit) => server.handle(path, init)))
  return mount(ProvidersView, {
    global: { plugins: [createPinia()] },
    attachTo: document.body,
  })
}

function cardFor(wrapper: ReturnType<typeof mountProviders>, name: string): DOMWrapper<Element> {
  const card = wrapper.findAll('article').find((item) => item.text().includes(name))
  if (card === undefined) {
    throw new Error('未找到供应商卡片: ' + name)
  }
  return card
}

async function settle(): Promise<void> {
  await flushPromises()
  await flushPromises()
}

describe('ProvidersView', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('loads tools and the provider summary without loading a tool list before selection', async () => {
    const server = new FakeServer()
    const wrapper = mountProviders(server)
    await settle()

    expect(getByText(wrapper, '选择一个工具')).toBeTruthy()
    expect(wrapper.text()).toContain('3 个工具')
    expect(wrapper.text()).toContain('2 个供应商 · 启用中 Anthropic 官方')
    expect(server.calls.some((call) => call.path.includes('tool_id='))).toBe(false)
  })

  it('loads the selected tool providers, shows active state and does not re-request a loading tool', async () => {
    const server = new FakeServer()
    const wrapper = mountProviders(server)
    await settle()

    const button = getByRole(wrapper, 'button', { name: 'Claude Code' })
    await button.trigger('click')
    await button.trigger('click')
    await settle()

    expect(server.calls.filter((call) => call.path === '/api/profiles?tool_id=claude-code')).toHaveLength(1)
    expect(wrapper.text()).toContain('Anthropic 官方')
    expect(wrapper.text()).toContain('Kimi K2')
    expect(cardFor(wrapper, 'Anthropic 官方').text()).toContain('已启用')
    expect(cardFor(wrapper, 'Kimi K2').text()).toContain('未启用')
    expect(cardFor(wrapper, 'Anthropic 官方').text()).toContain('https://api.anthropic.com')
    expect(cardFor(wrapper, 'Anthropic 官方').text()).toContain('claude-sonnet-4-5')
  })

  it('keeps the newest tool response when switching tools quickly', async () => {
    const server = new FakeServer({
      profiles: [profileA, profileB, profileC],
      bindings: [bindingA, bindingB, bindingC],
    })
    const claudeHold = server.defer('claude-code')
    const codexHold = server.defer('codex-cli')
    const wrapper = mountProviders(server)
    await settle()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await getByRole(wrapper, 'button', { name: 'Codex CLI' }).trigger('click')
    await flushPromises()

    codexHold.resolve(jsonResponse(server.listResponse('codex-cli')))
    await settle()
    const list = wrapper.find('[aria-labelledby="provider-list-title"]')
    expect(list.text()).toContain('Codex 供应商')

    claudeHold.resolve(jsonResponse(server.listResponse('claude-code')))
    await settle()
    expect(list.text()).toContain('Codex 供应商')
    expect(list.text()).not.toContain('Anthropic 官方')
  })

  it('creates a supplier, binds it to the current tool as inactive, and shows it in the list', async () => {
    const server = new FakeServer()
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    await getByRole(wrapper, 'button', { name: '新增供应商' }).trigger('click')
    const form = wrapper.find('form')
    await form.find('input[type="text"]').setValue('新供应商')
    await form.find('select').setValue('openai')
    await form.find('input[type="url"]').setValue('https://api.example.com/v1')
    await form.find('textarea').setValue('gpt-5')
    await form.trigger('submit')
    await settle()

    const createCall = server.calls.find((call) => call.method === 'POST' && call.path === '/api/profiles')
    expect(createCall?.body).toMatchObject({
      name: '新供应商',
      protocol: 'openai',
      base_url: 'https://api.example.com/v1',
      models: [{ id: 'gpt-5', display_name: null }],
      secret: null,
    })
    expect(server.calls.some((call) => call.method === 'PUT' && call.path === '/api/tools/claude-code/profile')).toBe(true)
    expect(wrapper.find('form').exists()).toBe(false)
    expect(cardFor(wrapper, '新供应商').text()).toContain('未启用')
  })

  it('edits a supplier, keeps the active binding, and supports explicitly clearing the secret', async () => {
    const server = new FakeServer()
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    let card = cardFor(wrapper, 'Anthropic 官方')
    await getByRole(card, 'button', { name: '编辑' }).trigger('click')
    const form = wrapper.find('form')
    await form.find('input[type="text"]').setValue('Anthropic 官方（改）')
    await form.trigger('submit')
    await settle()

    const patches = server.calls.filter((call) => call.method === 'PATCH')
    expect(patches[0]?.body).toMatchObject({ name: 'Anthropic 官方（改）' })
    expect(patches[0]?.body).not.toHaveProperty('secret')
    card = cardFor(wrapper, 'Anthropic 官方（改）')
    expect(card.text()).toContain('已启用')

    await getByRole(card, 'button', { name: '编辑' }).trigger('click')
    const formAgain = wrapper.find('form')
    await formAgain.find('input[type="checkbox"]').setValue(true)
    await formAgain.trigger('submit')
    await settle()

    const allPatches = server.calls.filter((call) => call.method === 'PATCH')
    expect(allPatches[1]?.body).toMatchObject({ secret: null })
    expect(cardFor(wrapper, 'Anthropic 官方（改）').text()).toContain('未设置')
  })

  it('copies a supplier and removes only the selected binding', async () => {
    const server = new FakeServer()
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    await getByRole(cardFor(wrapper, 'Anthropic 官方'), 'button', { name: '复制' }).trigger('click')
    await settle()

    expect(server.calls.some((call) => call.method === 'POST' && call.path === '/api/profiles/profile-a/copy')).toBe(true)
    expect(cardFor(wrapper, 'Anthropic 官方 (副本)').text()).toContain('未启用')
    const bindCall = server.calls.find((call) => call.method === 'PUT' && call.path === '/api/tools/claude-code/profile')
    expect(bindCall?.body).toMatchObject({ profile_id: 'profile-copy-1' })

    await getByRole(cardFor(wrapper, 'Kimi K2'), 'button', { name: '从工具移除' }).trigger('click')
    await settle()

    expect(server.calls.some((call) => call.method === 'DELETE' && call.path === '/api/tools/claude-code/profiles/profile-b')).toBe(true)
    expect(wrapper.text()).not.toContain('Kimi K2')
    expect(server.profiles.some((profile) => profile.id === 'profile-b')).toBe(true)
  })

  it('requires a second confirmation when deleting a supplier that is still in use', async () => {
    const server = new FakeServer()
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    await getByRole(cardFor(wrapper, 'Anthropic 官方'), 'button', { name: '删除' }).trigger('click')
    let dialog = wrapper.find('[role="alertdialog"]')
    expect(dialog.text()).toContain('删除供应商？')

    await getByRole(dialog, 'button', { name: '删除' }).trigger('click')
    await settle()

    dialog = wrapper.find('[role="alertdialog"]')
    expect(dialog.text()).toContain('供应商仍被使用')
    expect(dialog.text()).toContain('Claude Code')
    expect(dialog.text()).toContain('已卸载')

    await getByRole(dialog, 'button', { name: '仍然删除' }).trigger('click')
    await settle()

    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    const deleteCalls = server.calls.filter((call) => call.method === 'DELETE' && call.path.startsWith('/api/profiles/profile-a'))
    expect(deleteCalls[0]?.path).toBe('/api/profiles/profile-a')
    expect(deleteCalls[1]?.path).toBe('/api/profiles/profile-a?confirm=true')
    expect(server.profiles.some((profile) => profile.id === 'profile-a')).toBe(false)
  })

  it('shows health-check loading, renders the result, and clears it after switching tools', async () => {
    const server = new FakeServer()
    const gate = server.deferHealth()
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    const healthButton = getByRole(cardFor(wrapper, 'Anthropic 官方'), 'button', { name: '健康检查' })
    await healthButton.trigger('click')
    await flushPromises()

    expect(cardFor(wrapper, 'Anthropic 官方').text()).toContain('正在检测…')
    expect(getByRole(cardFor(wrapper, 'Anthropic 官方'), 'button', { name: '健康检查' }).attributes('disabled')).toBeDefined()

    gate.resolve()
    await settle()

    const resultText = cardFor(wrapper, 'Anthropic 官方').text()
    expect(resultText).toContain('连接正常')
    expect(resultText).toContain('428 ms')
    expect(resultText).toContain('claude-sonnet-4-5')

    await getByRole(wrapper, 'button', { name: 'Codex CLI' }).trigger('click')
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    expect(cardFor(wrapper, 'Anthropic 官方').text()).toContain('尚未检测')
    expect(cardFor(wrapper, 'Anthropic 官方').text()).not.toContain('连接正常')
  })

  it('shows empty and list-error states without hiding the tool list', async () => {
    const server = new FakeServer({ profiles: [profileA, profileB], bindings: [] })
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    expect(wrapper.text()).toContain('还没有绑定供应商')

    server.listErrorTool = 'codex-cli'
    await getByRole(wrapper, 'button', { name: 'Codex CLI' }).trigger('click')
    await settle()

    expect(wrapper.text()).toContain('供应商列表读取失败')
    expect(getByRole(wrapper, 'button', { name: 'Claude Code' })).toBeTruthy()
  })

  it('closes the delete dialog with Escape and returns focus to the trigger', async () => {
    const server = new FakeServer()
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    const deleteButton = getByRole(cardFor(wrapper, 'Anthropic 官方'), 'button', { name: '删除' })
    ;(deleteButton.element as HTMLElement).focus()
    await deleteButton.trigger('click')
    await settle()
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await settle()

    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    expect(document.activeElement).toBe(deleteButton.element)
  })

  it('keeps the form open and compensates when binding the new supplier fails', async () => {
    const server = new FakeServer()
    server.failBind = true
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    await getByRole(wrapper, 'button', { name: '新增供应商' }).trigger('click')
    const form = wrapper.find('form')
    await form.find('input[type="text"]').setValue('绑定失败供应商')
    await form.find('input[type="url"]').setValue('https://api.example.com/v1')
    await form.trigger('submit')
    await settle()

    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.find('[role="alert"]').text()).toContain('已创建，但绑定失败')
    expect(server.calls.some((call) => call.method === 'DELETE' && call.path === '/api/profiles/profile-created-1?confirm=true')).toBe(true)
    expect(server.profiles.some((profile) => profile.id === 'profile-created-1')).toBe(false)
  })

  it('renders a non-connected health result with a readable warning', async () => {
    const server = new FakeServer({
      health: {
        ...defaultHealth,
        status: 'SECRET_MISSING',
        attempted: false,
        duration_ms: null,
        message: '档案引用的密钥不存在',
      },
    })
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    await getByRole(cardFor(wrapper, 'Anthropic 官方'), 'button', { name: '健康检查' }).trigger('click')
    await settle()

    const text = cardFor(wrapper, 'Anthropic 官方').text()
    expect(text).toContain('缺少密钥')
    expect(text).toContain('档案引用的密钥不存在')
    expect(text).toContain('未发起请求')
  })
  it('opens the switch preview from an inactive provider card', async () => {
    const writeCapable = makeTool({
      capabilities: { ...capabilities, write: true, write_mode: 'managed_fields' },
    })
    const server = new FakeServer({
      tools: [writeCapable, codexTool, brokenTool],
    })
    const wrapper = mountProviders(server)
    await settle()
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await settle()

    await getByRole(wrapper, 'button', { name: '切换 Kimi K2' }).trigger('click')
    await settle()

    expect(server.calls.some((call) => call.path === '/api/switch/preview')).toBe(true)
    expect(wrapper.text()).toContain('切换供应商')
    expect(wrapper.text()).toContain('字段变更')
  })
})

