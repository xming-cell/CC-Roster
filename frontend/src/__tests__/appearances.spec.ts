import { describe, expect, it } from 'vitest'

import type { ToolView } from '../api/tools'
import {
  contrastRatio,
  defaultAppearance,
  resolveAppearance,
} from '../utils/appearances'

const capabilities: ToolView['capabilities'] = {
  read: true,
  write: false,
  sessions: false,
  launch: false,
  write_mode: 'none',
}

function makeTool(
  id: string,
  provider: string | null = 'Anthropic',
  model: string | null = 'sonnet',
): ToolView {
  return {
    id,
    display_name: id,
    status: 'ok',
    installed: true,
    configured: true,
    version: null,
    provider,
    base_url: null,
    model,
    is_third_party: false,
    config_path: null,
    last_modified: null,
    has_secret: false,
    secret_preview: null,
    warnings: [],
    capabilities,
  }
}

function rgbDistance(first: string, second: string): number {
  const channels = (color: string): [number, number, number] => [
    Number.parseInt(color.slice(1, 3), 16),
    Number.parseInt(color.slice(3, 5), 16),
    Number.parseInt(color.slice(5, 7), 16),
  ]
  const [leftRed, leftGreen, leftBlue] = channels(first)
  const [rightRed, rightGreen, rightBlue] = channels(second)
  return Math.sqrt(
    (leftRed - rightRed) ** 2 +
      (leftGreen - rightGreen) ** 2 +
      (leftBlue - rightBlue) ** 2,
  )
}

describe('friend appearance defaults', () => {
  it('is deterministic by tool id and keeps its identity hue when provider or model changes', () => {
    const base = makeTool('claude-code')
    const changedProfile = makeTool('claude-code', 'OpenAI', 'gpt-5')
    const tools = ['claude-code', 'codex-cli', 'gemini-cli', 'cursor', 'opencode'].map((id) =>
      makeTool(id),
    )
    const appearancesById = new Map(tools.map((tool) => [tool.id, defaultAppearance(tool)]))

    expect(defaultAppearance(base)).toEqual(defaultAppearance(base))
    expect(defaultAppearance(base).accentLight).toBe(defaultAppearance(changedProfile).accentLight)
    expect(defaultAppearance(base).accentDark).toBe(defaultAppearance(changedProfile).accentDark)
    expect(defaultAppearance(base).secondaryLight).not.toBe(
      defaultAppearance(changedProfile).secondaryLight,
    )
    expect([...tools].reverse().map(defaultAppearance)).toEqual(
      [...tools].reverse().map((tool) => appearancesById.get(tool.id)),
    )
    expect(defaultAppearance(makeTool('unlisted-tool', null, null))).toEqual(
      defaultAppearance(makeTool('unlisted-tool', null, null)),
    )
  })

  it('keeps five representative friend colors measurably distinct and AA readable', () => {
    const tools = ['claude-code', 'codex-cli', 'gemini-cli', 'cursor', 'opencode'].map((id) =>
      makeTool(id),
    )
    const appearances = tools.map(defaultAppearance)
    const colors = appearances.map((appearance) => appearance.accentLight)
    const distances = colors.flatMap((color, index) =>
      colors.slice(index + 1).map((other) => rgbDistance(color, other)),
    )

    expect(Math.min(...distances)).toBeGreaterThan(50)
    for (const appearance of appearances) {
      expect(contrastRatio(appearance.accentLight, '#F2F3F5')).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(appearance.accentDark, '#1D2129')).toBeGreaterThanOrEqual(4.5)
      expect(
        contrastRatio(appearance.avatarForegroundLight, appearance.avatarBackgroundLight),
      ).toBeGreaterThanOrEqual(4.5)
      expect(
        contrastRatio(appearance.avatarForegroundDark, appearance.avatarBackgroundDark),
      ).toBeGreaterThanOrEqual(4.5)
      expect(
        contrastRatio(appearance.chatForegroundLight, appearance.chatBackgroundLight),
      ).toBeGreaterThanOrEqual(4.5)
      expect(
        contrastRatio(appearance.chatForegroundDark, appearance.chatBackgroundDark),
      ).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('applies each saved override without changing another tool default', () => {
    const tool = makeTool('claude-code')
    const other = makeTool('codex-cli')
    const override = {
      accent_color: '#FFCC00',
      background_color: '#EEE0D0',
      bubble_preset: 'compact' as const,
    }

    const changed = resolveAppearance(tool, override)

    expect(changed.bubblePreset).toBe('compact')
    expect(changed.chatBackgroundLight).toBe('#EEE0D0')
    expect(changed.accentLight).not.toBe(defaultAppearance(tool).accentLight)
    expect(resolveAppearance(other)).toEqual(defaultAppearance(other))
  })
})
