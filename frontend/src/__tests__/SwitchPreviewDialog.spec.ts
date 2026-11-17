import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { ProfileView } from '../api/profiles'
import type { RollbackResponse } from '../api/snapshots'
import type { SwitchApplyResponse, SwitchPreviewResponse } from '../api/switch'
import type { ToolView } from '../api/tools'
import SwitchPreviewDialog from '../components/SwitchPreviewDialog.vue'
import { getByRole, getByText } from './dom'

const NOW = '2026-11-17T10:00:00+00:00'
const TARGET = '/home/me/.claude/settings.json'
const HASH = 'a'.repeat(64)

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
  model: 'claude-sonnet-4-5',
  is_third_party: false,
  config_path: TARGET,
  last_modified: NOW,
  has_secret: true,
  secret_preview: 'sk-a...cdef',
  warnings: [],
  capabilities: { read: true, write: true, sessions: false, launch: false, write_mode: 'managed_fields' },
}

const profile: ProfileView = {
  id: 'profile-b',
  name: 'Kimi K2',
  protocol: 'openai',
  base_url: 'https://api.moonshot.cn/v1',
  models: [{ id: 'kimi-k2-0905-preview', display_name: null }],
  created_at: NOW,
  updated_at: NOW,
  has_secret: true,
  secret_preview: 'sk-m...71c8',
  secret_backend: 'keyring',
  used_by: [],
  warnings: [],
}

const preview: SwitchPreviewResponse = {
  tool_id: 'claude-code',
  profile_id: 'profile-b',
  model: 'kimi-k2-0905-preview',
  available_models: [{ id: 'kimi-k2-0905-preview', display_name: null }],
  files: [
    {
      path: TARGET,
      format: 'json',
      action: 'updated',
      before_sha256: HASH,
      after_sha256: 'b'.repeat(64),
      before_size: 10,
      after_size: 12,
      changes: [
        { path: TARGET, field: 'model', action: 'set', before: 'claude-opus-4', after: 'claude-sonnet-4' },
        { path: TARGET, field: 'api_key', action: 'set', before: 'sk-••••9f2c', after: 'sk-••••4a71' },
      ],
    },
  ],
  blockers: [],
  warnings: [],
  restart_required: true,
  restart_message: 'Claude Code 需要重启',
  observations: [{ path: TARGET, exists: true, sha256: HASH, size: 10, mtime_ns: 1 }],
  preview_digest: 'c'.repeat(64),
  can_apply: true,
}

const applyResult: SwitchApplyResponse = {
  tool_id: 'claude-code',
  profile_id: 'profile-b',
  snapshot_id: 'snapshot-1',
  audit_id: 'audit-1',
  files: [{ path: TARGET, action: 'updated', sha256: 'd'.repeat(64), size: 12 }],
  binding: {
    tool_id: 'claude-code',
    profile_id: 'profile-b',
    bound_at: NOW,
    active: true,
    applied_at: NOW,
    snapshot_id: 'snapshot-1',
  },
  warnings: [],
  restart_required: true,
  restart_message: 'Claude Code 需要重启',
  applied_at: NOW,
}

const rollbackResult: RollbackResponse = {
  snapshot_id: 'snapshot-1',
  pre_rollback_snapshot_id: 'snapshot-2',
  files: [{ path: TARGET, action: 'restored', sha256: HASH, size: 10 }],
}

interface CallRecord {
  url: string
  body: Record<string, unknown>
}

function makeServer(options: {
  preview?: SwitchPreviewResponse
  apply?: { status: number; body: unknown }
  rollback?: RollbackResponse
} = {}) {
  const calls: CallRecord[] = []
  const previewBody = options.preview ?? preview
  const applyBody = options.apply ?? { status: 200, body: applyResult }
  const rollbackBody = options.rollback ?? rollbackResult

  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const body =
        typeof init?.body === 'string'
          ? (JSON.parse(init.body) as Record<string, unknown>)
          : {}
      calls.push({ url, body })
      if (url === '/api/switch/preview') {
        return Promise.resolve(jsonResponse(previewBody))
      }
      if (url === '/api/switch/apply') {
        return Promise.resolve(jsonResponse(applyBody.body, applyBody.status))
      }
      if (url.startsWith('/api/snapshots/') && url.endsWith('/rollback')) {
        return Promise.resolve(jsonResponse(rollbackBody))
      }
      return Promise.reject(new Error(`unexpected request: ${url}`))
    }),
  )
  return calls
}

function mountDialog() {
  return mount(SwitchPreviewDialog, {
    props: { tool, profile },
    global: { plugins: [createPinia()] },
    attachTo: document.body,
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('SwitchPreviewDialog', () => {
  it('shows the field diff and restart notice after preview', async () => {
    makeServer()
    const wrapper = mountDialog()
    await flushPromises()

    expect(getByText(wrapper, '字段变更').exists()).toBe(true)
    expect(getByText(wrapper, 'model').exists()).toBe(true)
    expect(getByText(wrapper, 'claude-sonnet-4').exists()).toBe(true)
    expect(getByText(wrapper, '重启后生效').exists()).toBe(true)
    expect(getByRole(wrapper, 'button', { name: '应用切换' }).exists()).toBe(true)
  })

  it('closes without applying when cancelled', async () => {
    const calls = makeServer()
    const wrapper = mountDialog()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '取消' }).trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(calls.map((call) => call.url)).toEqual(['/api/switch/preview'])
  })

  it('applies with the preview digest and shows the snapshot', async () => {
    const calls = makeServer()
    const wrapper = mountDialog()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '应用切换' }).trigger('click')
    await flushPromises()

    const applyCall = calls.find((call) => call.url === '/api/switch/apply')
    expect(applyCall?.body.preview_digest).toBe('c'.repeat(64))
    expect(applyCall?.body.observations).toEqual(preview.observations)
    expect(getByText(wrapper, '切换完成').exists()).toBe(true)
    expect(getByText(wrapper, 'snapshot-1').exists()).toBe(true)
    expect(getByText(wrapper, 'audit-1').exists()).toBe(true)
  })

  it('turns a stale preview into a conflict that can be rechecked', async () => {
    const calls = makeServer({
      apply: {
        status: 409,
        body: { code: 'SWITCH_PREVIEW_STALE', message: '目标文件在预览后发生变化' },
      },
    })
    const wrapper = mountDialog()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '应用切换' }).trigger('click')
    await flushPromises()

    expect(getByText(wrapper, '预览已失效').exists()).toBe(true)
    expect(getByText(wrapper, '未写入').exists()).toBe(true)

    await getByRole(wrapper, 'button', { name: '重新检查' }).trigger('click')
    await flushPromises()

    expect(calls.filter((call) => call.url === '/api/switch/preview')).toHaveLength(2)
  })

  it('disables apply when the preview has blockers', async () => {
    makeServer({
      preview: {
        ...preview,
        can_apply: false,
        blockers: [
          { code: 'SECRET_MISSING', message: '供应商缺少密钥', path: TARGET },
        ],
      },
    })
    const wrapper = mountDialog()
    await flushPromises()

    expect(getByText(wrapper, '存在阻止应用的项').exists()).toBe(true)
    expect(getByRole(wrapper, 'button', { name: '应用切换' }).attributes('disabled')).toBeDefined()
  })

  it('rolls back after confirmation and reports both snapshots', async () => {
    const calls = makeServer()
    const wrapper = mountDialog()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '应用切换' }).trigger('click')
    await flushPromises()
    await getByRole(wrapper, 'button', { name: '回滚到快照' }).trigger('click')
    await getByRole(wrapper, 'button', { name: '确认回滚' }).trigger('click')
    await flushPromises()

    expect(calls.some((call) => call.url === '/api/snapshots/snapshot-1/rollback')).toBe(true)
    expect(wrapper.text()).toContain('已回滚到 snapshot-1')
    expect(wrapper.text()).toContain('snapshot-2')
  })
})


