import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, requestJson } from '../api/client'
import { getHealth } from '../api/health'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

describe('api client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('returns parsed data on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ status: 'ok' })))

    await expect(getHealth()).resolves.toEqual({ status: 'ok' })
  })

  it('normalizes HTTP errors into ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ code: 'VALIDATION_ERROR', message: '请求参数不合法' }, 422),
      ),
    )

    const caught = await getHealth().catch((error: unknown) => error)

    expect(caught).toBeInstanceOf(ApiError)
    expect(caught).toMatchObject({
      code: 'VALIDATION_ERROR',
      message: '请求参数不合法',
      status: 422,
      details: null,
    })
  })

  it('parses conflict details without changing the old error shape', async () => {
    const expected = {
      path: '/home/me/.claude/settings.json',
      exists: true,
      sha256: 'a'.repeat(64),
      size: 12,
      mtime_ns: 1,
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            code: 'WRITE_CONFLICT',
            message: '文件在预览后发生变化',
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
          409,
        ),
      ),
    )

    const caught = await getHealth().catch((error: unknown) => error)

    expect(caught).toBeInstanceOf(ApiError)
    expect(caught).toMatchObject({ code: 'WRITE_CONFLICT', status: 409 })
    expect((caught as ApiError).details?.conflicts?.[0]).toMatchObject({
      path: expected.path,
      reason: 'CONTENT_CHANGED',
    })
  })

  it('ignores malformed details instead of rejecting the error body', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            code: 'WRITE_CONFLICT',
            message: '文件在预览后发生变化',
            details: { conflicts: [{ path: 42 }] },
          },
          409,
        ),
      ),
    )

    const caught = await getHealth().catch((error: unknown) => error)

    expect(caught).toBeInstanceOf(ApiError)
    expect((caught as ApiError).details).toBeNull()
  })

  it('falls back when the error body is not JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: () => Promise.reject(new SyntaxError('not json')),
      } as unknown as Response),
    )

    const caught = await getHealth().catch((error: unknown) => error)

    expect(caught).toBeInstanceOf(ApiError)
    expect(caught).toMatchObject({ code: 'HTTP_ERROR', status: 502 })
  })

  it('normalizes network failures into ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const caught = await getHealth().catch((error: unknown) => error)

    expect(caught).toBeInstanceOf(ApiError)
    expect(caught).toMatchObject({ code: 'NETWORK_ERROR', status: null })
  })

  it('aborts and reports a timeout', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_path: string, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => reject(new Error('aborted')))
          }),
      ),
    )

    const pending = requestJson('/api/health', {}, { timeoutMs: 50 })
    const caught = pending.catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(50)

    expect(await caught).toBeInstanceOf(ApiError)
    expect(await caught).toMatchObject({ code: 'TIMEOUT', status: null })
  })
})