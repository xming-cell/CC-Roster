import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import type { SwitchPreviewResponse } from '../api/switch'
import SwitchPreviewDialog from '../components/SwitchPreviewDialog.vue'
import { getByRole, getByText } from './dom'

function makePreview(
  overrides: Partial<SwitchPreviewResponse> = {},
): SwitchPreviewResponse {
  const path = '/home/me/.claude/settings.json'
  return {
    tool_id: 'claude-code',
    profile_id: 'profile-1',
    model: 'claude-sonnet-4',
    available_models: [{ id: 'claude-sonnet-4', display_name: 'Sonnet' }],
    files: [
      {
        path,
        format: 'json',
        action: 'updated',
        before_sha256: 'a'.repeat(64),
        after_sha256: 'b'.repeat(64),
        before_size: 120,
        after_size: 140,
        changes: [
          {
            path: 'env.ANTHROPIC_BASE_URL',
            field: 'env.ANTHROPIC_BASE_URL',
            action: 'set',
            before: 'https://old.example.com',
            after: 'https://relay.example.com',
          },
          {
            path: 'env.ANTHROPIC_API_KEY',
            field: 'env.ANTHROPIC_API_KEY',
            action: 'remove',
            before: 'sk-a****cdef',
            after: null,
          },
        ],
      },
    ],
    blockers: [],
    warnings: [],
    restart_required: true,
    restart_message: 'Claude Code 需要重启后才会读取新的 settings.json',
    observations: [
      {
        path,
        exists: true,
        sha256: 'a'.repeat(64),
        size: 120,
        mtime_ns: 1,
      },
    ],
    preview_digest: 'c'.repeat(64),
    can_apply: true,
    ...overrides,
  }
}

function mountDialog(
  overrides: Partial<SwitchPreviewResponse> = {},
  props: Partial<{
    busy: boolean
    error: string | null
    errorCode: string | null
    details: {
      conflicts?: {
        path: string
        reason: 'MISSING' | 'CREATED' | 'CONTENT_CHANGED'
        expected: {
          path: string
          exists: boolean
          sha256: string | null
          size: number
          mtime_ns: number | null
        }
        actual: {
          path: string
          exists: boolean
          sha256: string | null
          size: number
          mtime_ns: number | null
        }
      }[]
      stale_paths?: string[]
    } | null
    profileName: string | null
  }> = {},
) {
  return mount(SwitchPreviewDialog, {
    props: {
      preview: makePreview(overrides),
      profileName: '主力档案',
      busy: false,
      error: null,
      errorCode: null,
      details: null,
      ...props,
    },
  })
}

describe('SwitchPreviewDialog', () => {
  it('renders file paths, field-level before / after values and the restart notice', () => {
    const wrapper = mountDialog()

    expect(getByRole(wrapper, 'dialog').attributes('aria-modal')).toBe('true')
    expect(getByRole(wrapper, 'heading', { name: '确认切换到「主力档案」？' })).toBeTruthy()
    expect(
      getByText(wrapper, 'Claude Code 需要重启后才会读取新的 settings.json'),
    ).toBeTruthy()
    expect(wrapper.text()).toContain('/home/me/.claude/settings.json')
    expect(wrapper.text()).toContain('env.ANTHROPIC_BASE_URL')
    expect(wrapper.text()).toContain('https://old.example.com')
    expect(wrapper.text()).toContain('https://relay.example.com')
    expect(wrapper.text()).toContain('删除')
    expect(wrapper.text()).toContain('（删除）')
  })

  it('disables confirmation when blockers exist', () => {
    const wrapper = mountDialog({
      can_apply: false,
      files: [],
      blockers: [
        {
          code: 'PARSE_ERROR',
          message: '第 1 行格式错误',
          path: '/home/me/.claude/settings.json',
        },
      ],
    })

    const confirm = getByRole(wrapper, 'button', { name: '确认应用' })
    expect(confirm.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('PARSE_ERROR')
    expect(wrapper.text()).toContain('第 1 行格式错误')
    expect(wrapper.text()).toContain('没有可应用的文件改动')
  })

  it('shows warnings and stale paths, then emits repreview', async () => {
    const wrapper = mountDialog(
      {
        can_apply: false,
        warnings: [{ code: 'MODEL_SHADOWED', message: '顶层 model 仍保留原值' }],
      },
      {
        error: '预览已过期, 档案或模型在预览后发生变化, 请重新预览',
        errorCode: 'SWITCH_PREVIEW_STALE',
        details: { stale_paths: ['/home/me/.claude/settings.json'] },
      },
    )

    expect(getByRole(wrapper, 'alert').text()).toContain('预览已过期')
    expect(wrapper.text()).toContain('MODEL_SHADOWED')
    expect(wrapper.text()).toContain('过期文件：/home/me/.claude/settings.json')

    await getByRole(wrapper, 'button', { name: '重新预览' }).trigger('click')

    expect(wrapper.emitted('repreview')).toHaveLength(1)
  })

  it('shows conflict paths and reasons, then emits repreview', async () => {
    const expected = {
      path: '/home/me/.claude/settings.json',
      exists: true,
      sha256: 'a'.repeat(64),
      size: 120,
      mtime_ns: 1,
    }
    const wrapper = mountDialog(
      { can_apply: false },
      {
        error: '1 个文件在预览后发生变化, 已拒绝写入',
        errorCode: 'WRITE_CONFLICT',
        details: {
          conflicts: [
            {
              path: expected.path,
              reason: 'CONTENT_CHANGED',
              expected,
              actual: { ...expected, sha256: 'b'.repeat(64) },
            },
          ],
        },
      },
    )

    expect(wrapper.text()).toContain(expected.path)
    expect(wrapper.text()).toContain('文件内容已变化')

    await getByRole(wrapper, 'button', { name: '重新预览' }).trigger('click')

    expect(wrapper.emitted('repreview')).toHaveLength(1)
  })

  it('emits cancel from the button and Escape without confirming', async () => {
    const wrapper = mountDialog()

    await getByRole(wrapper, 'button', { name: '取消' }).trigger('click')
    await getByRole(wrapper, 'dialog').trigger('keydown', { key: 'Escape' })

    expect(wrapper.emitted('cancel')).toHaveLength(2)
    expect(wrapper.emitted('confirm')).toBeUndefined()
  })

  it('shows the in-flight state and disables actions while applying', async () => {
    const wrapper = mountDialog({}, { busy: true })

    const confirm = getByRole(wrapper, 'button', { name: '应用中…' })
    expect(confirm.attributes('disabled')).toBeDefined()
    expect(getByRole(wrapper, 'button', { name: '取消' }).attributes('disabled')).toBeDefined()

    await confirm.trigger('click')
    expect(wrapper.emitted('confirm')).toBeUndefined()
  })
})
