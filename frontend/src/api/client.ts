const DEFAULT_TIMEOUT_MS = 10_000

export interface ApiErrorBody {
  code: string
  message: string
}

export interface FileObservation {
  path: string
  exists: boolean
  sha256: string | null
  size: number
  mtime_ns: number | null
}

export type FileConflictReason = 'MISSING' | 'CREATED' | 'CONTENT_CHANGED'

export interface FileConflictDetail {
  path: string
  reason: FileConflictReason
  expected: FileObservation
  actual: FileObservation
}

export interface ApiErrorDetails {
  conflicts?: FileConflictDetail[]
  stale_paths?: string[]
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number | null
  readonly details: ApiErrorDetails | null

  constructor(
    code: string,
    message: string,
    status: number | null = null,
    details: ApiErrorDetails | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
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
    return new ApiError(
      parsed.code,
      parsed.message,
      response.status,
      parseErrorDetails((body as Record<string, unknown>).details),
    )
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

function parseErrorDetails(value: unknown): ApiErrorDetails | null {
  if (typeof value !== 'object' || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  const details: ApiErrorDetails = {}

  if (Array.isArray(record.conflicts)) {
    const conflicts = record.conflicts
      .map(parseConflict)
      .filter((conflict): conflict is FileConflictDetail => conflict !== null)
    if (conflicts.length > 0) {
      details.conflicts = conflicts
    }
  }

  if (Array.isArray(record.stale_paths)) {
    const stalePaths = record.stale_paths.filter(
      (item): item is string => typeof item === 'string',
    )
    if (stalePaths.length > 0) {
      details.stale_paths = stalePaths
    }
  }

  return Object.keys(details).length > 0 ? details : null
}

function parseConflict(value: unknown): FileConflictDetail | null {
  if (typeof value !== 'object' || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  if (typeof record.path !== 'string' || !isConflictReason(record.reason)) {
    return null
  }
  const expected = parseObservation(record.expected)
  const actual = parseObservation(record.actual)
  if (expected === null || actual === null) {
    return null
  }
  return { path: record.path, reason: record.reason, expected, actual }
}

function isConflictReason(value: unknown): value is FileConflictReason {
  return value === 'MISSING' || value === 'CREATED' || value === 'CONTENT_CHANGED'
}

function parseObservation(value: unknown): FileObservation | null {
  if (typeof value !== 'object' || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  if (
    typeof record.path !== 'string' ||
    typeof record.exists !== 'boolean' ||
    typeof record.size !== 'number' ||
    (record.sha256 !== null && typeof record.sha256 !== 'string') ||
    (record.mtime_ns !== null && typeof record.mtime_ns !== 'number')
  ) {
    return null
  }
  return {
    path: record.path,
    exists: record.exists,
    sha256: record.sha256,
    size: record.size,
    mtime_ns: record.mtime_ns,
  }
}
