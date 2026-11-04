import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import App from '../App.vue'

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        json: () => Promise.resolve({ status: 'ok' }),
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders backend status', async () => {
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.text()).toContain('backend: ok')
  })
})