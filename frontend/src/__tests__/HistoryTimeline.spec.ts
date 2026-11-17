import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import type { SessionMessage } from '../api/sessions'
import HistoryTimeline from '../components/HistoryTimeline.vue'
import { getByRole, getByText } from './dom'

const NOW = '2026-11-17T10:00:00+00:00'

function message(overrides: Partial<SessionMessage> & { id: string; role: SessionMessage['role'] }): SessionMessage {
  return {
    timestamp: NOW,
    content: '',
    tool_name: null,
    is_error: false,
    raw_type: null,
    ...overrides,
  }
}

function mountTimeline(messages: SessionMessage[], hasMore = false) {
  return mount(HistoryTimeline, {
    props: {
      title: '修复构建失败',
      sessionId: 'session-1',
      messages,
      loading: false,
      error: null,
      warnings: [],
      hasMore,
      totalMessages: messages.length,
    },
  })
}

describe('HistoryTimeline', () => {
  it('renders user, assistant and system messages', () => {
    const wrapper = mountTimeline([
      message({ id: 'u1', role: 'user', content: '帮我排查构建失败' }),
      message({ id: 'a1', role: 'assistant', content: '是依赖冲突。' }),
      message({ id: 's1', role: 'system', content: '会话在这里中断' }),
    ])

    expect(getByText(wrapper, '帮我排查构建失败').exists()).toBe(true)
    expect(getByText(wrapper, '是依赖冲突。').exists()).toBe(true)
    expect(getByText(wrapper, '会话在这里中断').exists()).toBe(true)
  })

  it('collapses tool calls and expands their raw output', async () => {
    const wrapper = mountTimeline([
      message({ id: 't1', role: 'tool_result', tool_name: 'shell', content: 'npm run build\nexit 1' }),
    ])

    expect(wrapper.find('pre').exists()).toBe(false)
    expect(wrapper.text()).toContain('shell · npm run build')

    await wrapper.find('button.process__row').trigger('click')

    expect(wrapper.find('pre').text()).toContain('exit 1')
  })

  it('labels unknown events with their raw type', async () => {
    const wrapper = mountTimeline([
      message({ id: 'x1', role: 'unknown', content: '自定义补丁事件', raw_type: 'patch' }),
    ])

    expect(wrapper.text()).toContain('raw_type: patch')
    await wrapper.find('button.process__row').trigger('click')
    expect(wrapper.find('pre').text()).toContain('自定义补丁事件')
  })

  it('shows load-earlier only when more messages exist', async () => {
    const more = mountTimeline([message({ id: 'u1', role: 'user', content: 'hi' })], true)
    expect(getByRole(more, 'button', { name: '加载更早的消息' }).exists()).toBe(true)

    const earliest = mountTimeline([message({ id: 'u1', role: 'user', content: 'hi' })], false)
    expect(earliest.text()).toContain('已到最早一条')
  })
})
