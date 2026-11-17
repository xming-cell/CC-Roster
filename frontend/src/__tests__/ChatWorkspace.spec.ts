import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { ChatSessionView } from '../api/chat'
import type { ProfileListResponse } from '../api/profiles'
import type { ToolView } from '../api/tools'
import ChatWorkspace from '../components/ChatWorkspace.vue'
import { getByText } from './dom'

const NOW = '2026-11-17T10:00:00+00:00'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

const tool: ToolView = {
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
  last_modified: NOW,
  has_secret: true,
  secret_preview: 'sk-a...cdef',
  warnings: [],
  capabilities: {
    read: true,
    write: true,
    sessions: true,
    launch: false,
    write_mode: 'managed_fields',
    reasoning_effort: true,
    reasoning_effort_levels: ['low', 'medium', 'high'],
  },
}

const profileList: ProfileListResponse = {
  profiles: [
    {
      id: 'profile-1',
      name: 'Anthropic 官方',
      protocol: 'anthropic',
      base_url: 'https://api.anthropic.com',
      models: [
        { id: 'claude-sonnet-4', display_name: null },
        { id: 'claude-opus-4', display_name: null },
      ],
      created_at: NOW,
      updated_at: NOW,
      has_secret: true,
      secret_preview: 'sk-a...cdef',
      secret_backend: 'file',
      used_by: [],
      warnings: [],
    },
  ],
  bindings: [
    {
      tool_id: 'claude-code',
      profile_id: 'profile-1',
      bound_at: NOW,
      active: true,
      applied_at: null,
      snapshot_id: null,
    },
  ],
  secret_store: { backend: 'file', fallback: false, message: null },
  warnings: [],
}

const session: ChatSessionView = {
  id: 'session-1',
  tool_id: 'claude-code',
  profile_id: 'profile-1',
  project_dir: 'D:/projects/demo',
  title: '旧会话',
  status: 'idle',
  model: null,
  reasoning_effort: null,
  messages: [],
  created_at: NOW,
  updated_at: NOW,
}

interface CallRecord {
  url: string
  method: string
  body: Record<string, unknown>
}

function makeServer(options: { sessions?: ChatSessionView[]; tool?: ToolView } = {}) {
  const calls: CallRecord[] = []
  const sessions = options.sessions ?? []
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      const body =
        typeof init?.body === 'string' ? (JSON.parse(init.body) as Record<string, unknown>) : {}
      calls.push({ url, method, body })
      if (url === '/api/chat/sessions' && method === 'GET') {
        return Promise.resolve(jsonResponse({ sessions }))
      }
      if (url === '/api/chat/sessions' && method === 'POST') {
        return Promise.resolve(
          jsonResponse({ ...session, id: 'session-new', ...body, messages: [] }, 201),
        )
      }
      if (url.startsWith('/api/chat/sessions/') && method === 'GET') {
        return Promise.resolve(jsonResponse(sessions[0] ?? session))
      }
      if (url.startsWith('/api/chat/sessions/') && method === 'PATCH') {
        return Promise.resolve(jsonResponse({ ...(sessions[0] ?? session), ...body }))
      }
      if (url.startsWith('/api/profiles')) {
        return Promise.resolve(jsonResponse(profileList))
      }
      return Promise.reject(new Error('unexpected request: ' + url))
    }),
  )
  return calls
}

function mountWorkspace(customTool: ToolView = tool) {
  return mount(ChatWorkspace, {
    props: { tool: customTool },
    global: { plugins: [createPinia()] },
    attachTo: document.body,
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('ChatWorkspace', () => {
  it('shows a read-only fallback for tools without chat support', async () => {
    makeServer()
    const wrapper = mountWorkspace({
      ...tool,
      capabilities: { ...tool.capabilities, sessions: false },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('这个工具不支持应用内对话')
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('asks for a project directory only when the tool has no earlier session', async () => {
    const calls = makeServer({ sessions: [] })
    const wrapper = mountWorkspace()
    await flushPromises()

    await getByText(wrapper, '新建会话').trigger('click')
    expect(wrapper.find('#project-dir-input').exists()).toBe(true)

    await wrapper.find('#project-dir-input').setValue('D:/projects/new')
    await getByText(wrapper, '创建会话').trigger('click')
    await flushPromises()

    const create = calls.find((call) => call.url === '/api/chat/sessions' && call.method === 'POST')
    expect(create?.body.project_dir).toBe('D:/projects/new')
    expect(create?.body.profile_id).toBe('profile-1')
  })

  it('creates a session in one click using the remembered project directory', async () => {
    const calls = makeServer({ sessions: [session] })
    const wrapper = mountWorkspace()
    await flushPromises()

    await wrapper.find('[aria-label="新建会话"]').trigger('click')
    await flushPromises()

    const create = calls.find((call) => call.url === '/api/chat/sessions' && call.method === 'POST')
    expect(create?.body.project_dir).toBe('D:/projects/demo')
    expect(wrapper.find('#project-dir-input').exists()).toBe(false)
  })

  it('switches the session model from the context chip', async () => {
    const calls = makeServer({ sessions: [session] })
    const wrapper = mountWorkspace()
    await flushPromises()

    await wrapper.findAll('button.context__chip')[0]?.trigger('click')
    await getByText(wrapper, 'claude-opus-4').trigger('click')
    await flushPromises()

    const patch = calls.find((call) => call.method === 'PATCH')
    expect(patch?.body.model).toBe('claude-opus-4')
  })

  it('hides the effort chip when the tool does not declare that capability', async () => {
    makeServer({ sessions: [session] })
    const wrapper = mountWorkspace({
      ...tool,
      capabilities: {
        ...tool.capabilities,
        reasoning_effort: false,
        reasoning_effort_levels: [],
      },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('思考强度')
  })
})
