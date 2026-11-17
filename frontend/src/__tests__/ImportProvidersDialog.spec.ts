import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { ProfileImportPreview, ProfileImportResult } from '../api/profileImport'
import ImportProvidersDialog from '../components/ImportProvidersDialog.vue'
import { getByRole, getByText } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

const validPreview: ProfileImportPreview = {
  schema_version: 1,
  items: [
    { index: 0, name: '甲', status: 'new', reasons: [], conflict_profile_id: null },
    { index: 1, name: '乙', status: 'new', reasons: [], conflict_profile_id: null },
  ],
  totals: { new: 2, duplicate: 0, invalid: 0 },
  can_import: true,
}

const invalidPreview: ProfileImportPreview = {
  schema_version: 1,
  items: [
    { index: 0, name: '甲', status: 'new', reasons: [], conflict_profile_id: null },
    {
      index: 1,
      name: '坏协议',
      status: 'invalid',
      reasons: ['protocol: 只支持 anthropic / openai'],
      conflict_profile_id: null,
    },
  ],
  totals: { new: 1, duplicate: 0, invalid: 1 },
  can_import: false,
}

const importResult: ProfileImportResult = {
  imported: 2,
  overwritten: 0,
  skipped: 0,
  profile_ids: ['profile-a', 'profile-b'],
}

interface CallRecord {
  url: string
  body: Record<string, unknown>
}

function makeServer(options: {
  preview?: { status: number; body: unknown }
  import?: { status: number; body: unknown }
} = {}) {
  const calls: CallRecord[] = []
  const preview = options.preview ?? { status: 200, body: validPreview }
  const imported = options.import ?? { status: 201, body: importResult }
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const body = typeof init?.body === 'string' ? (JSON.parse(init.body) as Record<string, unknown>) : {}
      calls.push({ url, body })
      if (url === '/api/profiles/import/preview') {
        return Promise.resolve(jsonResponse(preview.body, preview.status))
      }
      if (url === '/api/profiles/import') {
        return Promise.resolve(jsonResponse(imported.body, imported.status))
      }
      return Promise.reject(new Error(`unexpected request: ${url}`))
    }),
  )
  return calls
}

function mountDialog() {
  return mount(ImportProvidersDialog, {
    global: { plugins: [createPinia()] },
    attachTo: document.body,
  })
}

async function selectFile(
  wrapper: VueWrapper,
  name = 'demo.json',
  text = '{"schema_version":1,"profiles":[]}',
): Promise<void> {
  const file = new File([text], name, { type: 'application/json' })
  const input = wrapper.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  await input.trigger('change')
  await flushPromises()
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('ImportProvidersDialog', () => {
  it('previews new items and enables confirm', async () => {
    makeServer()
    const wrapper = mountDialog()

    await selectFile(wrapper)

    expect(wrapper.text()).toContain('新增')
    expect(getByText(wrapper, '甲').exists()).toBe(true)
    expect(getByRole(wrapper, 'button', { name: '确认导入' }).attributes('disabled')).toBeUndefined()
  })

  it('disables confirm when a preview contains invalid items', async () => {
    makeServer({ preview: { status: 200, body: invalidPreview } })
    const wrapper = mountDialog()

    await selectFile(wrapper)

    expect(wrapper.text()).toContain('protocol: 只支持 anthropic / openai')
    expect(wrapper.text()).toContain('确认导入不可用')
    expect(getByRole(wrapper, 'button', { name: '确认导入' }).attributes('disabled')).toBeDefined()
  })

  it('imports with the selected duplicate policy', async () => {
    const calls = makeServer()
    const wrapper = mountDialog()
    await selectFile(wrapper)

    await wrapper.findAll('input[type="radio"]')[1]?.setValue(true)
    await getByRole(wrapper, 'button', { name: '确认导入' }).trigger('click')
    await flushPromises()

    const importCall = calls.find((call) => call.url === '/api/profiles/import')
    expect(importCall?.body.policy).toBe('overwrite')
    expect(wrapper.emitted('imported')).toHaveLength(1)
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('shows a readable error when the file is not valid JSON', async () => {
    makeServer({
      preview: { status: 422, body: { code: 'IMPORT_INVALID_JSON', message: '文件不是合法 JSON' } },
    })
    const wrapper = mountDialog()

    await selectFile(wrapper)

    expect(wrapper.text()).toContain('文件不是合法 JSON')
    expect(wrapper.text()).toContain('未写入')
    expect(wrapper.text()).toContain('IMPORT_INVALID_JSON')
    expect(getByRole(wrapper, 'button', { name: '重新选择' }).exists()).toBe(true)
  })

  it('rejects non-json files without calling the backend', async () => {
    const calls = makeServer()
    const wrapper = mountDialog()

    await selectFile(wrapper, 'notes.txt')

    expect(calls).toHaveLength(0)
    expect(wrapper.text()).toContain('请选择 .json 文件')
  })
})
