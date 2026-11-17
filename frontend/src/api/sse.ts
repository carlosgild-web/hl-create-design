import type { ChatEvent } from './types'

/** Split a server-sent-events byte stream into `{event, data}` blocks. */
export async function* parseSse(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<{ event: string; data: unknown }> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      let end: number
      while ((end = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, end)
        buffer = buffer.slice(end + 2)
        const parsed = parseBlock(block)
        if (parsed) yield parsed
      }
      if (done) break
    }
    const rest = parseBlock(buffer.trim())
    if (rest) yield rest
  } finally {
    reader.releaseLock()
  }
}

function parseBlock(block: string): { event: string; data: unknown } | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
  }
  if (data.length === 0) return null
  try {
    return { event, data: JSON.parse(data.join('\n')) }
  } catch {
    return null
  }
}

export type ChatRequest = {
  message: string
  conversation_id: string | null
  language: 'en' | 'es'
  form: Record<string, string>
}

/** `POST /api/chat` and yield its events. EventSource can't POST, so this uses fetch. */
export async function* streamChat(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`Chat failed: HTTP ${response.status}`)
  }
  for await (const { event, data } of parseSse(response.body)) {
    yield { type: event, data } as ChatEvent
  }
}
