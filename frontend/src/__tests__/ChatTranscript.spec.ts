import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import type { ChatMessage } from '../api/chat'
import ChatTranscript from '../components/ChatTranscript.vue'
import { getByText } from './dom'

const NOW = '2026-11-17T10:00:00+00:00'

function message(overrides: Partial<ChatMessage> & { id: string; role: ChatMessage['role'] }): ChatMessage {
  return {
    content: '',
    created_at: NOW,
    tool_name: null,
    is_error: false,
    ...overrides,
  }
}

describe('ChatTranscript', () => {
  it('renders user and assistant messages', () => {
    const wrapper = mount(ChatTranscript, {
      props: {
        messages: [
          message({ id: 'u1', role: 'user', content: '帮我读一下 README' }),
          message({ id: 'a1', role: 'assistant', content: '已经读完，项目结构清晰。' }),
        ],
        streaming: null,
      },
    })

    expect(getByText(wrapper, '帮我读一下 README').exists()).toBe(true)
    expect(getByText(wrapper, '已经读完，项目结构清晰。').exists()).toBe(true)
  })

  it('collapses tool calls by default and expands on click', async () => {
    const wrapper = mount(ChatTranscript, {
      props: {
        messages: [
          message({ id: 't1', role: 'tool', tool_name: 'shell', content: 'ls -la\nexit code 0' }),
        ],
        streaming: null,
      },
    })

    expect(wrapper.find('pre').exists()).toBe(false)
    expect(wrapper.text()).toContain('shell · ls -la')

    await wrapper.find('button.process__row').trigger('click')

    expect(wrapper.find('pre').exists()).toBe(true)
    expect(wrapper.find('pre').text()).toContain('exit code 0')
  })

  it('groups consecutive tool calls into one section', () => {
    const wrapper = mount(ChatTranscript, {
      props: {
        messages: [
          message({ id: 't1', role: 'tool', tool_name: 'shell', content: 'ls' }),
          message({ id: 't2', role: 'tool', tool_name: 'read', content: 'README.md' }),
          message({ id: 'a1', role: 'assistant', content: '完成' }),
        ],
        streaming: null,
      },
    })

    expect(wrapper.findAll('section.process')).toHaveLength(1)
    expect(wrapper.text()).toContain('shell · ls')
    expect(wrapper.text()).toContain('read · README.md')
  })

  it('shows the streaming status and partial answer', () => {
    const wrapper = mount(ChatTranscript, {
      props: {
        messages: [],
        streaming: { content: '', status: '思考中', tools: [] },
      },
    })

    expect(wrapper.text()).toContain('思考中')

    const withText = mount(ChatTranscript, {
      props: {
        messages: [],
        streaming: { content: '正在读取配置', status: null, tools: [] },
      },
    })
    expect(withText.text()).toContain('正在读取配置')
    expect(withText.find('.caret').exists()).toBe(true)
  })
})
