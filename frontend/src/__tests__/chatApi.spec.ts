import { afterEach, describe, expect, it, vi } from 'vitest'

import { streamChatMessage } from '../api/chat'
import type { ChatEvent } from '../api/chat'

function sse(events: object[]): string {
  return events.map((event) => 'data: ' + JSON.stringify(event) + '\n\n').join('')
}

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
  return { ok: true, status: 200, body } as unknown as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamChatMessage', () => {
  it('parses SSE events split across chunks', async () => {
    const payload = sse([
      { type: 'status', status: 'running', message: '思考中' },
      { type: 'token', content: '你好' },
      { type: 'done', content: null },
    ])
    const cut = payload.length - 12
    vi.stubGlobal('fetch', () => Promise.resolve(streamResponse([payload.slice(0, cut), payload.slice(cut)])))

    const events: ChatEvent[] = []
    await streamChatMessage('session-1', 'hi', (event) => events.push(event))

    expect(events.map((event) => event.type)).toEqual(['status', 'token', 'done'])
    expect(events[1]?.content).toBe('你好')
  })

  it('raises a readable error for a failed request', async () => {
    vi.stubGlobal(
      'fetch',
      () =>
        Promise.resolve({
          ok: false,
          status: 409,
          json: () => Promise.resolve({ code: 'CHAT_BUSY', message: '这个对话正在执行' }),
        } as unknown as Response),
    )

    await expect(streamChatMessage('session-1', 'hi', () => undefined)).rejects.toThrow(
      '这个对话正在执行',
    )
  })
})
