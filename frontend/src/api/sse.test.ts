import { describe, expect, it } from 'vitest'

import { parseSse } from './sse'

function streamOf(...chunks: string[]) {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(encoder.encode(c)))
      controller.close()
    },
  })
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const out: { event: string; data: unknown }[] = []
  for await (const item of parseSse(stream)) out.push(item)
  return out
}

describe('parseSse', () => {
  it('parses events', async () => {
    const events = await collect(
      streamOf('event: conversation\ndata: {"id":"c1"}\n\nevent: done\ndata: {"status":"answered"}\n\n'),
    )
    expect(events).toEqual([
      { event: 'conversation', data: { id: 'c1' } },
      { event: 'done', data: { status: 'answered' } },
    ])
  })

  it('handles an event split across chunks, CRLF and non-ASCII text', async () => {
    const events = await collect(
      streamOf('event: message\r\ndata: {"content":"Revisi', 'ón ñ"}\r\n\r\n'),
    )
    expect(events).toEqual([{ event: 'message', data: { content: 'Revisión ñ' } }])
  })

  it('skips blocks without data and data that is not JSON', async () => {
    const events = await collect(streamOf(': keep-alive\n\nevent: x\ndata: nope\n\nevent: ok\ndata: 1\n\n'))
    expect(events).toEqual([{ event: 'ok', data: 1 }])
  })
})
