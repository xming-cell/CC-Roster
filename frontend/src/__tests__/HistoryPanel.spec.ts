import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import type { ToolSessionSummary } from '../api/sessions'
import HistoryPanel from '../components/HistoryPanel.vue'
import { getByText } from './dom'

const NOW = '2026-11-17T10:00:00+00:00'

function session(overrides: Partial<ToolSessionSummary> & { id: string; title: string }): ToolSessionSummary {
  return {
    tool_id: 'claude-code',
    project_path: 'D:/projects/demo',
    started_at: NOW,
    updated_at: NOW,
    message_count: 12,
    warnings: [],
    ...overrides,
  }
}

function mountPanel(sessions: ToolSessionSummary[]) {
  return mount(HistoryPanel, {
    props: {
      sessions,
      selectedId: null,
      loading: false,
      loaded: true,
      error: null,
      warnings: [],
    },
  })
}

describe('HistoryPanel', () => {
  it('groups sessions by project and labels unknown projects', () => {
    const wrapper = mountPanel([
      session({ id: 's1', title: '修复构建', project_path: 'D:/projects/demo' }),
      session({ id: 's2', title: '旧记录', project_path: null }),
    ])

    expect(wrapper.text()).toContain('demo')
    expect(wrapper.text()).toContain('未知项目')
    expect(wrapper.text()).toContain('修复构建')
    expect(wrapper.text()).toContain('旧记录')
  })

  it('emits the selected session id', async () => {
    const wrapper = mountPanel([session({ id: 's1', title: '修复构建' })])

    await getByText(wrapper, '修复构建').trigger('click')

    expect(wrapper.emitted('select')?.[0]).toEqual(['s1'])
  })
})
