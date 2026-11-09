const DEFAULT_TIMEOUT_MS = 10_000

export interface ApiErrorBody {
  code: string
  message: string
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number | null

  constructor(code: string, message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

export interface RequestOptions {
  timeoutMs?: number
}

export async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS)

  let response: Response
  try {
    response = await fetch(path, { ...init, signal: controller.signal })
  } catch {
    if (controller.signal.aborted) {
      throw new ApiError('TIMEOUT', '请求超时，请稍后重试')
    }
    throw new ApiError('NETWORK_ERROR', '无法连接后端服务')
  } finally {
    clearTimeout(timer)
  }

  if (!response.ok) {
    throw await toApiError(response)
  }

  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError('INVALID_RESPONSE', '后端返回了无法解析的响应', response.status)
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    // 非 JSON 错误响应走兜底文案
  }

  const parsed = parseErrorBody(body)
  if (parsed !== null) {
    return new ApiError(parsed.code, parsed.message, response.status)
  }
  return new ApiError('HTTP_ERROR', `请求失败（HTTP ${response.status}）`, response.status)
}

function parseErrorBody(value: unknown): ApiErrorBody | null {
  if (typeof value !== 'object' || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  if (typeof record.code !== 'string' || typeof record.message !== 'string') {
    return null
  }
  return { code: record.code, message: record.message }
}