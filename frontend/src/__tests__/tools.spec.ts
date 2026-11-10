import { describe, expect, it } from 'vitest'

import type { ToolView } from '../api/tools'
import { normalizeStatus, sortToolsByLastModified, statusDescription } from '../utils/tools'

const capabilities: ToolView['capabilities'] = {
  read: true,
  write: false,
  sessions: false,
  launch: false,
  write_mode: 'none',
}

function makeTool(overrides: Partial<ToolView>): ToolView {
  return {
    id: 'claude-code',
    display_name: 'Claude Code',
    status: 'ok',
    installed: true,
    configured: true,
    version: null,
    provider: 'Anthropic',
    base_url: 'https://api.anthropic.com',
    model: 'claude-sonnet-4',
    is_third_party: false,
    config_path: '/home/me/.claude/settings.json',
    last_modified: '2023-11-14T22:13:20+00:00',
    has_secret: true,
    secret_preview: 'sk-a****cdef',
    warnings: [],
    capabilities,
    ...overrides,
  }
}

function ids(tools: ToolView[]): string[] {
  return tools.map((tool) => tool.id)
}

describe('sortToolsByLastModified', () => {
  it('sorts tools by last_modified descending', () => {
    const sorted = sortToolsByLastModified([
      makeTool({ id: 'old', last_modified: '2023-01-01T00:00:00+00:00' }),
      makeTool({ id: 'new', last_modified: '2024-01-01T00:00:00+00:00' }),
    ])

    expect(ids(sorted)).toEqual(['new', 'old'])
  })

  it('puts null and unparsable timestamps last, ordered by display_name', () => {
    const sorted = sortToolsByLastModified([
      makeTool({ id: 'null', display_name: 'Zulu', last_modified: null }),
      makeTool({ id: 'valid', display_name: 'Yankee', last_modified: '2024-01-01T00:00:00+00:00' }),
      makeTool({ id: 'invalid', display_name: 'Alpha', last_modified: 'not-a-date' }),
    ])

    expect(ids(sorted)).toEqual(['valid', 'invalid', 'null'])
  })

  it('breaks equal timestamps by display_name and then id', () => {
    const sorted = sortToolsByLastModified([
      makeTool({
        id: 'zulu',
        display_name: 'Twin',
        last_modified: '2024-01-01T00:00:00+00:00',
      }),
      makeTool({
        id: 'alpha',
        display_name: 'Twin',
        last_modified: '2024-01-01T00:00:00+00:00',
      }),
      makeTool({
        id: 'bravo',
        display_name: 'Alpha',
        last_modified: '2024-01-01T00:00:00+00:00',
      }),
    ])

    expect(ids(sorted)).toEqual(['bravo', 'alpha', 'zulu'])
  })
})

describe('normalizeStatus', () => {
  it('falls back to error for unknown runtime statuses', () => {
    expect(normalizeStatus('mystery')).toBe('error')
  })
})

describe('statusDescription', () => {
  it('shows provider and model for a configured tool', () => {
    expect(statusDescription(makeTool({}))).toBe('Anthropic / claude-sonnet-4')
  })

  it('falls back to 已配置 when provider and model are missing', () => {
    expect(statusDescription(makeTool({ provider: null, model: null }))).toBe('已配置')
  })

  it('describes an installed but unconfigured tool', () => {
    expect(
      statusDescription(
        makeTool({
          status: 'unconfigured',
          configured: false,
          provider: null,
          model: null,
        }),
      ),
    ).toBe('已安装，尚未配置')
  })

  it('shows the first warning message for a broken tool', () => {
    expect(
      statusDescription(
        makeTool({
          status: 'error',
          warnings: [
            { code: 'PARSE_ERROR', message: 'settings.json 格式错误' },
            { code: 'UNKNOWN_FORMAT', message: '未知结构' },
          ],
        }),
      ),
    ).toBe('settings.json 格式错误')
  })

  it('falls back to 配置解析失败 when a broken tool has no warnings', () => {
    expect(statusDescription(makeTool({ status: 'error', warnings: [] }))).toBe('配置解析失败')
  })
})