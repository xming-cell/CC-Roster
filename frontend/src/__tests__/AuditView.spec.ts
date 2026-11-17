import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { AuditEntry } from '../api/audit'
import type { ToolView } from '../api/tools'
import AuditView from '../views/AuditView.vue'
import { getByRole, getByText } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) } as unknown as Response
}

const NOW = '2026-11-17T08:42:00+00:00'
const tool: ToolView = {
  id: 'claude-code', display_name: 'Claude Code', status: 'ok', installed: true, configured: true,
  version: null, provider: 'Anthropic', base_url: 'https://api.anthropic.com', model: 'claude-sonnet-4-5',
  is_third_party: false, config_path: '/home/.claude/settings.json', last_modified: NOW, has_secret: true,
  secret_preview: 'sk-a...cdef', warnings: [],
  capabilities: { read: true, write: true, sessions: false, launch: false, write_mode: 'managed_fields' },
}
const secondTool: ToolView = { ...tool, id: 'codex-cli', display_name: 'Codex CLI', provider: 'OpenAI' }
const entries: AuditEntry[] = [
  {
    id: 'audit-1', created_at: NOW, action: 'apply', tool_id: 'claude-code', profile_id: 'profile-a',
    snapshot_id: '11111111-1111-4111-8111-111111111111', files: ['/home/.claude/settings.json'],
    fields: ['model', 'env.ANTHROPIC_BASE_URL'], result: 'success', message: '已应用并创建快照',
  },
  {
    id: 'audit-2', created_at: '2026-11-17T07:10:00+00:00', action: 'profile_import', tool_id: 'codex-cli',
    profile_id: null, snapshot_id: null, files: ['/home/.codex/profiles.json'], fields: ['models'],
    result: 'failed', message: '导入被拒绝',
  },
]

const profiles = {
  profiles: [{ id: 'profile-a', name: 'Anthropic 官方' }],
  bindings: [], secret_store: { backend: 'keyring', fallback: false, message: null }, warnings: [],
}

const snapshot = {
  schema_version: 1, id: '11111111-1111-4111-8111-111111111111', tool_id: 'claude-code', profile_id: 'profile-a',
  created_at: NOW, reason: 'apply', pinned: false,
  files: [{ path: '/home/.claude/settings.json', existed: true, sha256: 'a'.repeat(64), size: 42, mtime_ns: 1, mode: 420 }],
  changes: [{ path: '/home/.claude/settings.json', field: 'model', action: 'set', before: 'old-model', after: 'claude-sonnet-4-5' }],
}

type Call = { path: string; method: string }

function mountView(calls: Call[], options: { empty?: boolean; fail?: boolean } = {}) {
  vi.stubGlobal('fetch', vi.fn((input: string, init?: RequestInit) => {
    const path = String(input)
    calls.push({ path, method: init?.method ?? 'GET' })
    if (path === '/api/tools') return Promise.resolve(jsonResponse({ tools: [tool, secondTool], warnings: [] }))
    if (path === '/api/profiles') return Promise.resolve(jsonResponse(profiles))
    if (path.startsWith('/api/audit')) {
      if (options.fail) return Promise.resolve(jsonResponse({ code: 'AUDIT_UNREADABLE', message: '审计文件损坏' }, 500))
      return Promise.resolve(jsonResponse({ entries: options.empty ? [] : entries }))
    }
    if (path.startsWith('/api/snapshots/')) return Promise.resolve(jsonResponse(snapshot))
    return Promise.resolve(jsonResponse({}))
  }))
  return mount(AuditView, { global: { plugins: [createPinia()] } })
}

async function settle(): Promise<void> {
  await flushPromises()
  await flushPromises()
}

describe('AuditView', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('renders audit entries in a readable timeline and filters by tool', async () => {
    const calls: Call[] = []
    const wrapper = mountView(calls)
    await settle()

    expect(getByText(wrapper, '切换供应商')).toBeTruthy()
    expect(getByText(wrapper, '导入供应商')).toBeTruthy()
    expect(getByText(wrapper, 'Anthropic 官方')).toBeTruthy()
    expect(getByText(wrapper, '已应用并创建快照')).toBeTruthy()

    await getByRole(wrapper, 'button', { name: '筛选 Codex CLI' }).trigger('click')
    await settle()
    expect(calls.some((call) => call.path === '/api/audit?tool_id=codex-cli&limit=200')).toBe(true)
  })

  it('opens a snapshot entry and renders the change summary', async () => {
    const calls: Call[] = []
    const wrapper = mountView(calls)
    await settle()

    await getByRole(wrapper, 'button', { name: '查看快照' }).trigger('click')
    await settle()

    expect(calls.some((call) => call.path === '/api/snapshots/' + snapshot.id)).toBe(true)
    expect(wrapper.text()).toContain('快照详情')
    expect(wrapper.text()).toContain('字段变更')
    expect(wrapper.text()).toContain('claude-sonnet-4-5')
  })

  it('shows empty and error states without losing the page shell', async () => {
    const emptyWrapper = mountView([], { empty: true })
    await settle()
    expect(emptyWrapper.text()).toContain('没有符合条件的操作记录')

    vi.unstubAllGlobals()
    const errorWrapper = mountView([], { fail: true })
    await settle()
    expect(errorWrapper.text()).toContain('操作记录读取失败')
    expect(errorWrapper.text()).toContain('审计文件损坏')
    expect(errorWrapper.text()).toContain('操作记录')
  })
})
