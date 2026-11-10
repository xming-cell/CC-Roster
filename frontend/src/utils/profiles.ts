import type {
  ProfileProtocol,
  ProfileWarningCode,
  SecretBackend,
  ToolRef,
} from '../api/profiles'

export function protocolLabel(protocol: ProfileProtocol): string {
  return protocol === 'anthropic' ? 'Anthropic 协议' : 'OpenAI 协议'
}

export function secretBackendLabel(backend: SecretBackend | null): string {
  if (backend === 'keyring') {
    return '系统钥匙串'
  }
  if (backend === 'file') {
    return '本机文件'
  }
  return '未知后端'
}

export function warningLabel(code: ProfileWarningCode): string {
  return code === 'SECRET_MISSING' ? '密钥缺失' : '密钥存储异常'
}

export function usedByLabel(references: ToolRef[]): string {
  return references
    .map((reference) =>
      reference.installed ? reference.display_name : `${reference.display_name}（已不可用）`,
    )
    .join('、')
}