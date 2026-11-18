import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import ProjectDirPrompt from '../components/ProjectDirPrompt.vue'
import { getByRole } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) } as unknown as Response
}

function mountPrompt() {
  return mount(ProjectDirPrompt, {
    props: { busy: false, error: null },
    attachTo: document.body,
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('ProjectDirPrompt', () => {
  it('fills the selected path and still requires explicit creation', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn((path: string, init?: RequestInit) => {
      calls.push(String(path) + ':' + (init?.method ?? 'GET'))
      return Promise.resolve(jsonResponse({ path: 'D:\\projects\\demo', cancelled: false }))
    }))
    const wrapper = mountPrompt()

    await getByRole(wrapper, 'button', { name: '浏览项目目录' }).trigger('click')
    await flushPromises()

    const input = wrapper.find('input[type="text"]')
    expect((input.element as HTMLInputElement).value).toBe('D:\\projects\\demo')
    expect(calls).toEqual(['/api/system/pick-directory:POST'])
    expect(getByRole(wrapper, 'button', { name: '创建会话' }).attributes('disabled')).toBeUndefined()
    expect(wrapper.emitted('confirm')).toBeUndefined()
  })

  it('keeps the current value when the dialog is cancelled', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse({ path: null, cancelled: true }))))
    const wrapper = mountPrompt()
    await wrapper.find('input[type="text"]').setValue('D:\\existing')

    await getByRole(wrapper, 'button', { name: '浏览项目目录' }).trigger('click')
    await flushPromises()

    expect((wrapper.find('input[type="text"]').element as HTMLInputElement).value).toBe('D:\\existing')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('ignores a second click while the native picker is open', async () => {
    let resolveFetch: ((value: Response) => void) | undefined
    const fetchMock = vi.fn<() => Promise<Response>>(() => new Promise<Response>((resolve) => { resolveFetch = resolve }))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mountPrompt()

    await getByRole(wrapper, 'button', { name: '浏览项目目录' }).trigger('click')
    expect(getByRole(wrapper, 'button', { name: '浏览项目目录' }).attributes('disabled')).toBeDefined()
    await getByRole(wrapper, 'button', { name: '浏览项目目录' }).trigger('click')
    expect(fetchMock).toHaveBeenCalledTimes(1)

    resolveFetch?.(jsonResponse({ path: null, cancelled: true }))
    await flushPromises()
  })

  it('falls back to manual input when the platform has no native picker', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(
      { code: 'DIRECTORY_PICKER_UNAVAILABLE', message: '当前平台没有可用的系统目录选择器' },
      501,
    ))))
    const wrapper = mountPrompt()

    await getByRole(wrapper, 'button', { name: '浏览项目目录' }).trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('请手动输入绝对路径')
    expect(wrapper.find('button[aria-label="浏览项目目录"]').exists()).toBe(false)
  })
})
