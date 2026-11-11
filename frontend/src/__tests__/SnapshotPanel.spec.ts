import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type {
  RollbackResponse,
  SnapshotListResponse,
  SnapshotSummary,
} from '../api/snapshots'
import SnapshotPanel from '../components/SnapshotPanel.vue'
import { getAllByRole, getByRole, getByText } from './dom'

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

const snapshotPath = '/home/me/.claude/settings.json'
const snapshotId = '11111111-1111-4111-8111-111111111111'
const secondId = '22222222-2222-4222-8222-222222222222'

const snapshotFile: SnapshotSummary['files'][number] = {
  path: snapshotPath,
  existed: true,
  sha256: 'a'.repeat(64),
  size: 120,
  mtime_ns: 1,
  mode: 420,
}

function makeSnapshot(overrides: Partial<SnapshotSummary> = {}): SnapshotSummary {
  return {
    id: snapshotId,
    tool_id: 'claude-code',
    profile_id: 'profile-1',
    created_at: '2026-11-11T09:30:00Z',
    reason: 'apply',
    pinned: false,
    file_count: 1,
    total_size: 120,
    files: [snapshotFile],
    changes: [
      {
        path: snapshotPath,
        field: 'env.ANTHROPIC_BASE_URL',
        action: 'set',
        before: 'https://old.example.com',
        after: 'https://relay.example.com',
      },
    ],
    ...overrides,
  }
}

function listBody(
  snapshots: SnapshotSummary[],
  warnings: SnapshotListResponse['warnings'] = [],
): SnapshotListResponse {
  return { snapshots, retention_limit: 20, warnings }
}

function makeRollback(overrides: Partial<RollbackResponse> = {}): RollbackResponse {
  return {
    snapshot_id: snapshotId,
    pre_rollback_snapshot_id: '33333333-3333-4333-8333-333333333333',
    files: [
      { path: snapshotPath, action: 'restored', sha256: 'a'.repeat(64), size: 120 },
      { path: '/home/me/.claude/removed.json', action: 'deleted', sha256: null, size: 0 },
      { path: '/home/me/.claude/same.json', action: 'unchanged', sha256: 'b'.repeat(64), size: 80 },
    ],
    ...overrides,
  }
}

function mountPanel(toolId = 'claude-code') {
  return mount(SnapshotPanel, {
    props: { toolId },
    global: { plugins: [createPinia()] },
    attachTo: document.body,
  })
}

describe('SnapshotPanel', () => {
  beforeEach(() => {
    calls = []
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lists snapshots with time, reason, files, change summary and pin state', async () => {
    installFetch(() =>
      jsonResponse(
        listBody([
          makeSnapshot(),
          makeSnapshot({
            id: secondId,
            created_at: '2026-11-11T10:00:00Z',
            reason: 'rollback',
            pinned: true,
            files: [{ ...snapshotFile, existed: false, sha256: null }],
            changes: [],
          }),
        ]),
      ),
    )
    const wrapper = mountPanel()
    await flushPromises()

    expect(getByRole(wrapper, 'heading', { name: '快照 / 回滚' })).toBeTruthy()
    expect(getByText(wrapper, '应用前快照')).toBeTruthy()
    expect(getByText(wrapper, '回滚前快照')).toBeTruthy()
    expect(getByText(wrapper, '未固定')).toBeTruthy()
    expect(getByText(wrapper, '已固定')).toBeTruthy()
    expect(wrapper.text()).toContain(snapshotPath)
    expect(wrapper.text()).toContain('env.ANTHROPIC_BASE_URL')
    expect(wrapper.text()).toContain('https://old.example.com')
    expect(wrapper.text()).toContain('https://relay.example.com')
    expect(wrapper.text()).toContain('（快照时不存在）')
    expect(wrapper.text()).toContain('无字段变更')
    expect(wrapper.text()).toContain('最多保留最近 20 份快照')
    expect(getAllByRole(wrapper, 'link')).toHaveLength(0)
  })

  it('shows the empty state without any download entry', async () => {
    installFetch(() => jsonResponse(listBody([])))
    const wrapper = mountPanel()
    await flushPromises()

    expect(getByText(wrapper, '暂无快照，应用档案后会自动生成')).toBeTruthy()
    expect(getAllByRole(wrapper, 'link')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('下载快照')
    expect(wrapper.text()).not.toContain('导出')
  })

  it('keeps list warnings visible', async () => {
    installFetch(() =>
      jsonResponse(
        listBody([makeSnapshot()], [
          { code: 'SNAPSHOT_UNREADABLE', message: '快照 222 元数据损坏' },
        ]),
      ),
    )
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('[aria-label="快照警告"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('SNAPSHOT_UNREADABLE')
    expect(wrapper.text()).toContain('快照 222 元数据损坏')
  })

  it('shows a readable error with retry after the initial request fails', async () => {
    let failing = true
    installFetch(() => {
      if (failing) {
        return Promise.reject(new TypeError('Failed to fetch'))
      }
      return jsonResponse(listBody([makeSnapshot()]))
    })
    const wrapper = mountPanel()
    await flushPromises()

    expect(getByRole(wrapper, 'alert').text()).toContain('无法连接后端服务')

    failing = false
    await getByRole(wrapper, 'button', { name: '重试' }).trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(snapshotId)
    expect(wrapper.text()).not.toContain('无法连接后端服务')
  })

  it('pins and unpins a snapshot with the requested state', async () => {
    let pinned = false
    installFetch((path, method, body) => {
      if (method === 'PATCH') {
        pinned = (body as { pinned: boolean }).pinned
        return jsonResponse({ ...makeSnapshot(), pinned })
      }
      return jsonResponse(listBody([makeSnapshot({ pinned })]))
    })
    const wrapper = mountPanel()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: `固定快照 ${snapshotId}` }).trigger('click')
    await flushPromises()

    expect(callsTo(`/api/snapshots/${snapshotId}`, 'PATCH')[0]?.body).toEqual({ pinned: true })
    expect(getByText(wrapper, '已固定')).toBeTruthy()

    await getByRole(wrapper, 'button', { name: `取消固定快照 ${snapshotId}` }).trigger('click')
    await flushPromises()

    expect(callsTo(`/api/snapshots/${snapshotId}`, 'PATCH')[1]?.body).toEqual({ pinned: false })
    expect(getByText(wrapper, '未固定')).toBeTruthy()
  })

  it('does not pretend a failed pin succeeded', async () => {
    installFetch((path, method) => {
      if (method === 'PATCH') {
        return jsonResponse({ code: 'SNAPSHOT_WRITE_FAILED', message: '快照固定失败' }, 500)
      }
      return jsonResponse(listBody([makeSnapshot()]))
    })
    const wrapper = mountPanel()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: `固定快照 ${snapshotId}` }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'alert').text()).toContain('快照固定失败')
    expect(getByText(wrapper, '未固定')).toBeTruthy()
    expect(wrapper.text()).not.toContain('已固定')
  })

  it('cancels the rollback dialog without sending a request', async () => {
    installFetch(() => jsonResponse(listBody([makeSnapshot()])))
    const wrapper = mountPanel()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: `回滚到快照 ${snapshotId}` }).trigger('click')
    const dialog = getByRole(wrapper, 'dialog')
    expect(dialog.attributes('aria-modal')).toBe('true')
    expect(dialog.text()).toContain(`确认回滚到快照 ${snapshotId}`)

    const cancel = getByRole(dialog, 'button', { name: '取消' })
    await flushPromises()
    expect(document.activeElement).toBe(cancel.element)

    await cancel.trigger('click')
    expect(callsTo(`/api/snapshots/${snapshotId}/rollback`, 'POST')).toHaveLength(0)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)

    await getByRole(wrapper, 'button', { name: `回滚到快照 ${snapshotId}` }).trigger('click')
    await getByRole(wrapper, 'dialog').trigger('keydown', { key: 'Escape' })
    expect(callsTo(`/api/snapshots/${snapshotId}/rollback`, 'POST')).toHaveLength(0)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('confirms rollback, shows the pre-rollback snapshot and refreshes the list', async () => {
    let snapshots = [makeSnapshot()]
    installFetch((path, method) => {
      if (method === 'POST' && path === `/api/snapshots/${snapshotId}/rollback`) {
        snapshots = [
          makeSnapshot({
            id: '33333333-3333-4333-8333-333333333333',
            reason: 'rollback',
          }),
        ]
        return jsonResponse(makeRollback())
      }
      return jsonResponse(listBody(snapshots))
    })
    const wrapper = mountPanel()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: `回滚到快照 ${snapshotId}` }).trigger('click')
    await getByRole(wrapper, 'button', { name: '确认回滚' }).trigger('click')
    await flushPromises()

    expect(callsTo(`/api/snapshots/${snapshotId}/rollback`, 'POST')).toHaveLength(1)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).toContain(`已回滚到快照 ${snapshotId}`)
    expect(wrapper.text()).toContain('33333333-3333-4333-8333-333333333333')
    expect(wrapper.text()).toContain(`${snapshotPath}（已恢复）`)
    expect(wrapper.text()).toContain('/home/me/.claude/removed.json（已删除）')
    expect(wrapper.text()).toContain('/home/me/.claude/same.json（未变化）')
    expect(calls.filter((call) => call.method === 'GET' && call.path.startsWith('/api/snapshots'))).toHaveLength(2)
    expect(wrapper.text()).toContain('回滚前快照')
  })

  it('keeps the dialog and reports the error when rollback fails', async () => {
    installFetch((path, method) => {
      if (method === 'POST') {
        return jsonResponse(
          { code: 'ROLLBACK_FAILED', message: '回滚失败, 已用预回滚快照还原' },
          500,
        )
      }
      return jsonResponse(listBody([makeSnapshot()]))
    })
    const wrapper = mountPanel()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: `回滚到快照 ${snapshotId}` }).trigger('click')
    await getByRole(wrapper, 'button', { name: '确认回滚' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'dialog')).toBeTruthy()
    expect(getByRole(wrapper, 'alert').text()).toContain('回滚失败')
    expect(wrapper.text()).not.toContain('已回滚到快照')
    expect(calls.filter((call) => call.method === 'GET' && call.path.startsWith('/api/snapshots'))).toHaveLength(1)
  })

  it('sends only one rollback request when confirmation is clicked twice', async () => {
    const pending = deferred<Response>()
    installFetch((path, method) => {
      if (method === 'POST') {
        return pending.promise
      }
      return jsonResponse(listBody([makeSnapshot()]))
    })
    const wrapper = mountPanel()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: `回滚到快照 ${snapshotId}` }).trigger('click')
    const confirm = getByRole(wrapper, 'button', { name: '确认回滚' })
    await confirm.trigger('click')
    await confirm.trigger('click')
    await flushPromises()

    expect(callsTo(`/api/snapshots/${snapshotId}/rollback`, 'POST')).toHaveLength(1)

    pending.resolve(jsonResponse(makeRollback()))
    await flushPromises()

    expect(wrapper.text()).toContain('已回滚到快照')
  })
})