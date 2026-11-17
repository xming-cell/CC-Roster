import { ApiError } from '../api/client'
import type { HealthCheckStatus, ProfileProtocol, ProfileView } from '../api/profiles'

export type HealthTone = 'success' | 'warning' | 'danger' | 'neutral'

export function protocolLabel(protocol: ProfileProtocol): string {
  return protocol === 'anthropic' ? 'Anthropic' : 'OpenAI 兼容'
}

export function secretStatusLabel(profile: ProfileView): string {
  return profile.has_secret ? '已配置' : '未设置'
}

export function secretPreviewLabel(profile: ProfileView): string {
  if (!profile.has_secret) {
    return '健康检查会提示缺少密钥'
  }
  return profile.secret_preview ?? '已配置（已脱敏）'
}

export function modelSummary(profile: ProfileView): string {
  if (profile.models.length === 0) {
    return '未设置模型'
  }
  return profile.models.map((model) => model.id).join(' · ')
}

export function formatDateTime(value: string | null): string {
  if (value === null) {
    return '未知'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

const HEALTH_LABELS: Record<HealthCheckStatus, string> = {
  CONNECTED: '连接正常',
  INVALID_CREDENTIALS: '凭据无效',
  INVALID_ADDRESS: '地址不可用',
  MODEL_NOT_FOUND: '模型不存在',
  TIMEOUT: '请求超时',
  RATE_LIMITED: '请求被限流',
  SECRET_MISSING: '缺少密钥',
  SECRET_STORE_ERROR: '密钥存储不可用',
  MODEL_REQUIRED: '需要模型',
  UNKNOWN: '检测失败',
}

export function healthStatusLabel(status: HealthCheckStatus): string {
  return HEALTH_LABELS[status]
}

export function healthTone(status: HealthCheckStatus): HealthTone {
  if (status === 'CONNECTED') {
    return 'success'
  }
  if (status === 'MODEL_REQUIRED' || status === 'SECRET_MISSING' || status === 'SECRET_STORE_ERROR') {
    return 'warning'
  }
  return 'danger'
}

export function errorText(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}
