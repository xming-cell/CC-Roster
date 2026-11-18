import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { UsageResponse } from '../api/usage'
import UsageView from '../views/UsageView.vue'
import { getByRole, getByText } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) } as unknown as Response
}

const usage: UsageResponse = {
  days: 7,
  records: [
    { date: '2026-11-17', tool_id: 'claude-code', model: 'claude-sonnet-4.5', calls: 42, input_tokens: 612300,
      output_tokens: 148200, estimated_cost: '3.480000', currency: 'USD', price_known: true },
    { date: '2026-11-17', tool_id: 'codex-cli', model: 'gpt-5.1-codex', calls: 18, input_tokens: 208700,
      output_tokens: 42900, estimated_cost: null, currency: 'USD', price_known: false },
    { date: '2026-11-16', tool_id: 'claude-code', model: 'claude-opus-4.1', calls: 12, input_tokens: 284600,
      output_tokens: 31500, estimated_cost: '4.960000', currency: 'USD', price_known: true },
  ],
  totals: { calls: 72, input_tokens: 1105600, output_tokens: 222600, estimated_cost: '8.440000', currency: 'USD', unknown_price_calls: 18 },
  pricing_note: '基于内置价格表估算',
  warnings: [{ code: 'UNKNOWN_PRICE', message: 'gpt-5.1-codex 没有内置价格' }],
}

const tools = {
  tools: [
    { id: 'claude-code', display_name: 'Claude Code' },
    { id: 'codex-cli', display_name: 'Codex CLI' },
  ],
  warnings: [],
}

function mountView(calls: { path: string }[], options: { empty?: boolean; fail?: boolean; allUnknown?: boolean } = {}) {
  vi.stubGlobal('fetch', vi.fn((input: string) => {
    const path = String(input)
    calls.push({ path })
    if (path === '/api/tools') return Promise.resolve(jsonResponse(tools))
    if (path.startsWith('/api/usage')) {
      if (options.fail) return Promise.resolve(jsonResponse({ code: 'USAGE_FAILED', message: '用量读取失败' }, 500))
      if (options.allUnknown) {
        return Promise.resolve(jsonResponse({
          ...usage,
          totals: { ...usage.totals, calls: 18, input_tokens: 208700, output_tokens: 42900, estimated_cost: '0.000000', unknown_price_calls: 18 },
        }))
      }
      return Promise.resolve(jsonResponse(options.empty ? {
        ...usage, records: [], totals: { ...usage.totals, calls: 0, input_tokens: 0, output_tokens: 0, estimated_cost: '0', unknown_price_calls: 0 }, warnings: [],
      } : usage))
    }
    return Promise.resolve(jsonResponse({}))
  }))
  return mount(UsageView, { global: { plugins: [createPinia()] } })
}

async function settle(): Promise<void> {
  await flushPromises()
  await flushPromises()
}

describe('UsageView', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows totals, unknown prices and the estimation notice', async () => {
    const calls: { path: string }[] = []
    const wrapper = mountView(calls)
    await settle()

    expect(getByText(wrapper, '72')).toBeTruthy()
    expect(wrapper.text()).toContain('$8.44')
    expect(wrapper.text()).toContain('18 次价格未知')
    expect(wrapper.text()).toContain('未知')
    expect(wrapper.text()).toContain('仅展示、不扣费')
    expect(wrapper.text()).toContain('gpt-5.1-codex 没有内置价格')
    expect(getByRole(wrapper, 'button', { name: '近 30 天' })).toBeTruthy()

    await getByRole(wrapper, 'button', { name: '近 30 天' }).trigger('click')
    await settle()
    expect(calls.some((call) => call.path === '/api/usage?days=30')).toBe(true)
  })

  it('shows unknown instead of zero when every call has unknown pricing', async () => {
    const wrapper = mountView([], { allUnknown: true })
    await settle()

    expect(wrapper.text()).toContain('估算花费')
    expect(wrapper.text()).toContain('未知价格未计入')
    expect(wrapper.text()).not.toContain('$0.00')
  })

  it('shows empty and error states without NaN or fake values', async () => {
    const emptyWrapper = mountView([], { empty: true })
    await settle()
    expect(emptyWrapper.text()).toContain('当前范围没有用量记录')
    expect(emptyWrapper.text()).not.toContain('NaN')

    vi.unstubAllGlobals()
    const errorWrapper = mountView([], { fail: true })
    await settle()
    expect(errorWrapper.text()).toContain('用量读取失败')
    expect(errorWrapper.text()).toContain('重试')
  })
})
