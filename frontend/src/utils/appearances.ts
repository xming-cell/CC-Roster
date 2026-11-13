import type { AppearanceOverride, BubblePreset } from '../api/appearances'
import type { ToolView } from '../api/tools'

export interface FriendAppearance {
  accentLight: string
  accentDark: string
  accentSoftLight: string
  accentSoftDark: string
  avatarBackgroundLight: string
  avatarBackgroundDark: string
  avatarForegroundLight: string
  avatarForegroundDark: string
  chatBackgroundLight: string
  chatBackgroundDark: string
  chatForegroundLight: string
  chatForegroundDark: string
  secondaryLight: string
  secondaryDark: string
  bubblePreset: BubblePreset
}

export type AppearanceStyle = Record<`--friend-${string}`, string>

const LIGHT_SURFACE = '#F2F3F5'
const DARK_SURFACE = '#1D2129'
const PRESETS: BubblePreset[] = ['soft', 'rounded', 'compact']
const IDENTITY_HUES: Record<string, number> = {
  'claude-code': 270,
  'codex-cli': 210,
  'gemini-cli': 30,
  cursor: 155,
  opencode: 330,
}

function hash(value: string): number {
  let result = 2166136261
  for (const character of value) {
    result = Math.imul(result ^ (character.codePointAt(0) ?? 0), 16777619) >>> 0
  }
  return result
}

function hslToHex(hue: number, saturation: number, lightness: number): string {
  const chroma = (1 - Math.abs(2 * lightness - 1)) * saturation
  const segment = hue / 60
  const secondary = chroma * (1 - Math.abs((segment % 2) - 1))
  const offset = lightness - chroma / 2
  const channels =
    segment < 1
      ? [chroma, secondary, 0]
      : segment < 2
        ? [secondary, chroma, 0]
        : segment < 3
          ? [0, chroma, secondary]
          : segment < 4
            ? [0, secondary, chroma]
            : segment < 5
              ? [secondary, 0, chroma]
              : [chroma, 0, secondary]
  return `#${channels.map((channel) => Math.round((channel + offset) * 255).toString(16).padStart(2, '0')).join('')}`.toUpperCase()
}

function rgb(hex: string): [number, number, number] {
  const channel = (index: number) => Number.parseInt(hex.slice(index, index + 2), 16) / 255
  return [channel(1), channel(3), channel(5)]
}

function luminance(color: string): number {
  const linear = (channel: number) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  const [red, green, blue] = rgb(color)
  return linear(red) * 0.2126 + linear(green) * 0.7152 + linear(blue) * 0.0722
}

export function contrastRatio(first: string, second: string): number {
  const firstLuminance = luminance(first)
  const secondLuminance = luminance(second)
  const brighter = Math.max(firstLuminance, secondLuminance)
  const darker = Math.min(firstLuminance, secondLuminance)
  return (brighter + 0.05) / (darker + 0.05)
}

function accessibleAccent(hue: number, dark: boolean): string {
  const surface = dark ? DARK_SURFACE : LIGHT_SURFACE
  const steps = dark
    ? Array.from({ length: 56 }, (_, index) => 45 + index)
    : Array.from({ length: 56 }, (_, index) => 55 - index)
  return (
    steps
      .map((lightness) => hslToHex(hue, 0.72, lightness / 100))
      .find((color) => contrastRatio(color, surface) >= 4.5) ?? (dark ? '#FFFFFF' : '#000000')
  )
}

function hslFromHex(hex: string): [number, number, number] {
  const [red, green, blue] = rgb(hex)
  const maximum = Math.max(red, green, blue)
  const minimum = Math.min(red, green, blue)
  const delta = maximum - minimum
  const lightness = (maximum + minimum) / 2
  let hue = 0
  if (delta !== 0) {
    if (maximum === red) {
      hue = 60 * (((green - blue) / delta) % 6)
    } else if (maximum === green) {
      hue = 60 * ((blue - red) / delta + 2)
    } else {
      hue = 60 * ((red - green) / delta + 4)
    }
  }
  return [(hue + 360) % 360, maximum === minimum ? 0 : delta / (1 - Math.abs(2 * lightness - 1)), lightness]
}

function contrastForeground(background: string): string {
  return contrastRatio(background, '#000000') >= contrastRatio(background, '#FFFFFF')
    ? '#000000'
    : '#FFFFFF'
}

function colorHue(hex: string | undefined, fallback: number): number {
  return hex === undefined ? fallback : hslFromHex(hex)[0]
}

export function defaultAppearance(tool: ToolView): FriendAppearance {
  const identityHue = IDENTITY_HUES[tool.id] ?? hash(tool.id) % 360
  const family = `${tool.provider ?? 'unknown'}:${tool.model ?? 'unknown'}`
  const secondaryHue = hash(family) % 360
  const lightAccent = accessibleAccent(identityHue, false)
  const darkAccent = accessibleAccent(identityHue, true)
  const lightBackground = hslToHex(secondaryHue, 0.24, 0.96)
  const darkBackground = hslToHex(secondaryHue, 0.22, 0.15)

  return {
    accentLight: lightAccent,
    accentDark: darkAccent,
    accentSoftLight: hslToHex(identityHue, 0.38, 0.94),
    accentSoftDark: hslToHex(identityHue, 0.38, 0.22),
    avatarBackgroundLight: lightAccent,
    avatarBackgroundDark: darkAccent,
    avatarForegroundLight: contrastForeground(lightAccent),
    avatarForegroundDark: contrastForeground(darkAccent),
    chatBackgroundLight: lightBackground,
    chatBackgroundDark: darkBackground,
    chatForegroundLight: contrastForeground(lightBackground),
    chatForegroundDark: contrastForeground(darkBackground),
    secondaryLight: accessibleAccent(secondaryHue, false),
    secondaryDark: accessibleAccent(secondaryHue, true),
    bubblePreset: PRESETS[hash(family) % PRESETS.length] ?? 'soft',
  }
}

export function resolveAppearance(
  tool: ToolView,
  override?: AppearanceOverride,
): FriendAppearance {
  const defaults = defaultAppearance(tool)
  const accentHue = colorHue(
    override?.accent_color ?? undefined,
    IDENTITY_HUES[tool.id] ?? hash(tool.id) % 360,
  )
  const accentLight = override?.accent_color
    ? accessibleAccent(accentHue, false)
    : defaults.accentLight
  const accentDark = override?.accent_color
    ? accessibleAccent(accentHue, true)
    : defaults.accentDark

  let chatBackgroundLight = defaults.chatBackgroundLight
  let chatBackgroundDark = defaults.chatBackgroundDark
  if (override?.background_color) {
    const [hue, saturation] = hslFromHex(override.background_color)
    chatBackgroundLight = override.background_color.toUpperCase()
    chatBackgroundDark = hslToHex(hue, Math.min(saturation, 0.35), 0.15)
  }

  return {
    ...defaults,
    accentLight,
    accentDark,
    avatarBackgroundLight: accentLight,
    avatarBackgroundDark: accentDark,
    avatarForegroundLight: contrastForeground(accentLight),
    avatarForegroundDark: contrastForeground(accentDark),
    chatBackgroundLight,
    chatBackgroundDark,
    chatForegroundLight: contrastForeground(chatBackgroundLight),
    chatForegroundDark: contrastForeground(chatBackgroundDark),
    bubblePreset: override?.bubble_preset ?? defaults.bubblePreset,
  }
}

export function appearanceStyle(appearance: FriendAppearance): AppearanceStyle {
  return {
    '--friend-accent-light': appearance.accentLight,
    '--friend-accent-dark': appearance.accentDark,
    '--friend-accent-soft-light': appearance.accentSoftLight,
    '--friend-accent-soft-dark': appearance.accentSoftDark,
    '--friend-avatar-background-light': appearance.avatarBackgroundLight,
    '--friend-avatar-background-dark': appearance.avatarBackgroundDark,
    '--friend-avatar-foreground-light': appearance.avatarForegroundLight,
    '--friend-avatar-foreground-dark': appearance.avatarForegroundDark,
    '--friend-chat-background-light': appearance.chatBackgroundLight,
    '--friend-chat-background-dark': appearance.chatBackgroundDark,
    '--friend-chat-foreground-light': appearance.chatForegroundLight,
    '--friend-chat-foreground-dark': appearance.chatForegroundDark,
    '--friend-secondary-light': appearance.secondaryLight,
    '--friend-secondary-dark': appearance.secondaryDark,
    '--friend-bubble-radius':
      appearance.bubblePreset === 'soft'
        ? '1.25rem'
        : appearance.bubblePreset === 'compact'
          ? '0.25rem'
          : '0.75rem',
  }
}
