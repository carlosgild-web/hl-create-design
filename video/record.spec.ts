/**
 * The Demo video take (decision 0028). Drives the running app (start.cmd, provider demo)
 * inside the 1920x1080 stage and shows each storyboard row when its captured event arrives.
 *
 *   npm run video:smoke   10-second clip: the stage layout at 1920x1080
 *   npm run video:demo    the take -> out/demo/{take.webm, events.json, shown.json, trace-turn-N.json}
 *
 * Capture: an init script wraps the app's fetch. Every SSE event of POST /api/chat, the
 * chat request itself, and the JSON of POST /api/actions and .../confirm go to Node with
 * their time, and are handed to the app only when Node returns: that is how a subtitle
 * stays on screen while the app shows that step. The app is not changed and the events
 * are not changed; only their delivery to the browser is paced.
 */
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import { captureEditor } from './kicad.mjs'
import { resolve as resolveLine, ROOT } from './lines.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const STAGE = { width: 1920, height: 1080 }
const TYPE_DELAY_MS = 50
const TURN_TIMEOUT_MS = 200_000
const PYTHON =
  process.env.VIDEO_PYTHON ||
  join(ROOT, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
// A Windows or home path on screen fails the take (acceptance check: no C:\MyData in frames).
// Checked on string values, not JSON text: there a newline after "directory:" reads "y:\n".
const PATH_RE = /(?<![A-Za-z])[A-Za-z]:\\[^\s\\]|\\Users\\|\/home\/|MyData/
const hasLocalPath = (value: unknown): boolean =>
  typeof value === 'string'
    ? PATH_RE.test(value)
    : value !== null && typeof value === 'object'
      ? Object.values(value).some(hasLocalPath)
      : false

type Storyboard = typeof import('./storyboard.json')
type Row = Storyboard['rows'][number] & {
  turn?: string
  on: { step?: string; event?: string; name?: string; auto?: boolean; code?: string; kind?: string; phase?: string; follow?: boolean }
  payload?: { from: string; pick?: string }
  callouts?: string[][]
  slide?: string
  layer?: string
}
type Captured = { type: string; data: any; status?: number; t_ms: number; turn: string | null; index: number }

const storyboard: Storyboard = JSON.parse(readFileSync(join(HERE, 'storyboard.json'), 'utf8'))
const CHAT_TYPES = new Set(['request', 'conversation', 'run', 'tool_call', 'tool_result', 'form_proposal', 'pending_action', 'thinking', 'message', 'notice', 'status', 'error', 'done'])

// ---------------------------------------------------------------- capture (all frames)

const CAPTURE = String.raw`(() => {
  if (location.pathname.startsWith('/__video')) return
  try {
    localStorage.setItem('hl-create-design.demo-guide', 'pill')
    localStorage.setItem('hl-create-design.lang', 'en')
  } catch {}
  const send = (event) => window.__videoEvent(event)
  const parse = (block) => {
    let type = 'message'; const data = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) type = line.slice(6).trim()
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (!data.length) return null
    try { return { type, data: JSON.parse(data.join('\n')) } } catch { return null }
  }
  const original = window.fetch.bind(window)
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input.url
    const method = (init.method || 'GET').toUpperCase()
    if (method === 'POST' && url.startsWith('/api/chat')) {
      await send({ type: 'request', data: JSON.parse(init.body) })
      const response = await original(input, init)
      if (!response.body) return response
      const reader = response.body.getReader()
      const decoder = new TextDecoder(), encoder = new TextEncoder()
      const body = new ReadableStream({
        async start(controller) {
          let buffer = ''
          for (;;) {
            const { value, done } = await reader.read()
            buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, '\n')
            let end
            while ((end = buffer.indexOf('\n\n')) !== -1) {
              const block = buffer.slice(0, end)
              buffer = buffer.slice(end + 2)
              const event = parse(block)
              if (event) await send(event)
              controller.enqueue(encoder.encode(block + '\n\n'))
            }
            if (done) break
          }
          const rest = parse(buffer.trim())
          if (rest) { await send(rest); controller.enqueue(encoder.encode(buffer.trim() + '\n\n')) }
          controller.close()
        },
      })
      return new Response(body, { status: response.status, statusText: response.statusText, headers: response.headers })
    }
    const confirm = /^\/api\/actions\/[^/?]+\/confirm/.test(url)
    if (method === 'POST' && (confirm || url === '/api/actions')) {
      const response = await original(input, init)
      const data = await response.clone().json().catch(() => null)
      await send({ type: confirm ? 'confirm' : 'action', data, status: response.status })
      return response
    }
    return original(input, init)
  }
  // P1: the preview dialog's "Project file" path is masked in the video.
  const mask = () => {
    for (const code of document.querySelectorAll('code[title]')) {
      if (!code.hasAttribute('data-video-masked')) {
        code.setAttribute('data-video-masked', '')
        code.style.filter = 'blur(7px)'
      }
    }
  }
  new MutationObserver(mask).observe(document, { childList: true, subtree: true })
})()`

// ---------------------------------------------------------------- the conductor

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

function pick(value: any, path?: string) {
  if (!path) return value
  for (const part of path.split('.')) {
    if (value == null) throw new Error(`payload path "${path}" not found`)
    value = value[/^\d+$/.test(part) ? Number(part) : part]
  }
  if (value === undefined) throw new Error(`payload path "${path}" not found`)
  return value
}

function holdMs(row: Row) {
  const chars = (row.subtitle || '').length
  return Math.min(Math.max(1400 + chars * 48, 2800), 8500) + (row.payload ? 1800 : 0)
}

function introspect(...args: string[]) {
  const out = execFileSync(PYTHON, [join(HERE, 'introspect.py'), ...args], { encoding: 'utf8' })
  return JSON.parse(out)
}

/** Rows are walked in order: a step row by the spec, an event row by its captured event. */
class Conductor {
  rows: Row[]
  cursor = 0
  t0 = 0
  turn: string | null = null
  turnText = ''
  events: Captured[] = []
  shown: Array<{ id: string; t_ms: number; hold_ms: number; subtitle: string; payload?: unknown; source?: unknown }> = []
  traces: any[] = []
  failure: Error | null = null
  /** Rejects on the first failure: races every wait of the spec. */
  readonly failed: Promise<never>
  private reject: (err: Error) => void = () => {}
  private chain: Promise<void> = Promise.resolve()
  private turnDone: Promise<void> = Promise.resolve()
  private finishTurn: () => void = () => {}
  private pendingTrace: Promise<void> = Promise.resolve()
  private last: Record<string, Captured> = {}

  constructor(
    private page: Page,
    private api: APIRequestContext,
    private outDir: string,
  ) {
    this.failed = new Promise<never>((_, reject) => (this.reject = reject))
    this.failed.catch(() => {}) // observed through until()
    let turn: string | undefined
    this.rows = (storyboard.rows as Row[]).map((row) => {
      const typed = row.on.step?.startsWith('typed:') ? row.on.step.slice(6) : undefined
      turn = typed ?? turn
      return { ...row, turn: row.turn ?? (row.on.event && CHAT_TYPES.has(row.on.event) ? turn : undefined) }
    })
  }

  setFailure(err: Error) {
    if (!this.failure) {
      this.failure = err
      this.reject(err)
    }
  }

  private fail(message: string): never {
    this.setFailure(new Error(message))
    throw this.failure
  }

  /** `p`, or the take's first failure, or a timeout. */
  async until<T>(p: Promise<T>, ms = TURN_TIMEOUT_MS, what = 'the app'): Promise<T> {
    let timer: ReturnType<typeof setTimeout> | undefined
    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error(`${what}: nothing after ${ms / 1000} s`)), ms)
    })
    try {
      return await Promise.race([p, this.failed, timeout])
    } finally {
      clearTimeout(timer)
    }
  }

  check() {
    if (this.failure) throw this.failure
  }

  now() {
    return Date.now() - this.t0
  }

  beginTurn(key: string, text: string) {
    this.turn = key
    this.turnText = text
    this.turnDone = new Promise((r) => (this.finishTurn = r))
  }

  /** The turn's done event has been handled, its trace saved, and its rows shown. */
  async waitTurn() {
    await this.turnDone
    await this.pendingTrace
    await this.chain
    this.check()
  }

  /** The result of the last confirmed card of `kind`, as the app received it. */
  lastConfirm(kind: string): any {
    const ev = [...this.events].reverse().find((e) => e.type === 'confirm' && e.data?.kind === kind)
    return ev?.data?.result ?? this.fail(`no confirmed ${kind} card in the take`)
  }

  async idle() {
    await this.chain
    this.check()
  }

  private matches(row: Row | undefined, ev: Captured) {
    if (!row || !row.on.event || row.on.event !== ev.type) return false
    if (row.turn && row.turn !== ev.turn) return false
    const d = ev.data ?? {}
    if (row.on.name && d.name !== row.on.name) return false
    if (row.on.auto !== undefined && !!d.auto !== row.on.auto) return false
    if (row.on.kind && d.kind !== row.on.kind) return false
    if (row.on.code && !(d.result?.errors ?? []).some((e: any) => e.code === row.on.code)) return false
    return true
  }

  /** The row at the cursor and the follow rows after it. */
  private take(): Row[] {
    const group = [this.rows[this.cursor++]]
    while (this.rows[this.cursor]?.on.follow) group.push(this.rows[this.cursor++])
    return group
  }

  private payloadFor(row: Row, ev?: Captured) {
    if (!row.payload) return undefined
    const { from, pick: path } = row.payload
    let source: any
    let value: any
    if (from === 'event') {
      if (!ev) this.fail(`row ${row.id}: payload from an event, but no event triggered it`)
      source = { from, index: ev.index, pick: path }
      value = pick(ev.data, path)
    } else if (from === 'request' || from === 'confirm' || from === 'action') {
      const captured = this.last[from] ?? this.fail(`row ${row.id}: no ${from} captured yet`)
      source = { from, index: captured.index, pick: path }
      value = pick(captured.data, path)
    } else if (from === 'trace') {
      const trace = this.traces.at(-1) ?? this.fail(`row ${row.id}: no trace saved yet`)
      source = { from, turn: this.traces.length, pick: path }
      value = pick(trace, path)
    } else if (from === 'introspect:intent') {
      value = introspect('intent', this.turnText)
      source = { from, args: ['intent', this.turnText] }
    } else if (from === 'introspect:fts') {
      const query = ev?.data?.arguments?.query ?? this.fail(`row ${row.id}: no search query`)
      value = introspect('fts', query, '--lang', ev.data.arguments.language || 'en')
      source = { from, args: ['fts', query] }
    } else {
      this.fail(`row ${row.id}: unknown payload source "${from}"`)
    }
    if (hasLocalPath(value)) this.fail(`row ${row.id}: the payload shows a local path`)
    const label = from === 'event' ? `SSE event: ${ev!.type}` : from === 'request' ? 'POST /api/chat (request body)'
      : from === 'confirm' ? `POST /api/actions/{id}/confirm → ${this.last.confirm?.status}` : from === 'action' ? 'POST /api/actions → 201'
      : from === 'trace' ? `GET /api/runs/${this.traces.at(-1)?.id}` : `video/introspect.py ${String(source.args[0])}`
    return { label, note: path ? `.${path}` : 'captured', value, source }
  }

  private async show(row: Row, ev?: Captured) {
    const callouts = (row.callouts ?? []).map(([file, symbol]) => resolveLine(file, symbol))
    const payload = this.payloadFor(row, ev)
    const slideData = row.slide ? this.slideData(row.slide) : undefined
    const cue = { id: row.id, subtitle: row.subtitle, layer: row.layer, callouts, payload, slide: row.slide, slideData }
    await this.page.evaluate((c) => (window as any).stage.show(c), cue)
    const hold = holdMs(row)
    this.shown.push({ id: row.id, t_ms: this.now(), hold_ms: hold, subtitle: row.subtitle, payload: payload?.value, source: payload?.source })
    await sleep(hold)
  }

  private slideData(name: string) {
    if (name === 'invariants' || name === 'close') return { invariants: invariants(), hot: [2, 3, 6] }
    if (name === 'trace') {
      const run = this.traces.at(-1) ?? this.fail('trace slide: no trace saved')
      const steps = (run.trace?.steps ?? []) as any[]
      return {
        id: run.id, model_calls: run.model_calls, status: run.status, provider: run.provider, model: run.model,
        max_iterations: run.trace?.max_iterations, tool_calls: steps.filter((s) => s.type === 'tool_call').length,
        steps: steps.map((s) => s.type === 'model_call'
          ? `model call ${s.iteration}: ${(s.tool_calls ?? []).map((c: any) => c.name).join(', ') || 'final message'}`
          : `  tool ${s.name}${s.auto ? ' (auto)' : ''} ok=${s.ok} ${Math.round(s.ms)} ms`),
      }
    }
    return {}
  }

  /** Called by the page (exposeBinding) for every captured event; returning releases it. */
  async onEvent(raw: { type: string; data: any; status?: number }) {
    const ev: Captured = { ...raw, t_ms: this.now(), turn: CHAT_TYPES.has(raw.type) ? this.turn : null, index: this.events.length }
    this.events.push(ev)
    this.last[ev.type] = ev
    try {
      await this.chain
      if (this.failure) return
      const before: Row[] = []
      const after: Row[] = []
      while (this.matches(this.rows[this.cursor], ev)) {
        const head = this.rows[this.cursor]
        ;(head.on.phase === 'before' ? before : after).push(...this.take())
      }
      if (!before.length && !after.length) {
        const later = this.rows.slice(this.cursor + 1).find((r) => this.matches(r, ev))
        const waiting = this.rows[this.cursor]
        if (later && waiting?.on.event && waiting.turn === ev.turn)
          this.fail(`row ${waiting.id} expected "${waiting.on.event}", but ${ev.type} for row ${later.id} came first`)
      }
      for (const row of before) await this.show(row, ev)
      if (ev.type === 'done') this.onDone(ev)
      this.chain = (async () => {
        await sleep(250) // the app renders the event first
        for (const row of after) await this.show(row, ev)
      })().catch((err) => this.setFailure(err))
    } catch (err) {
      this.setFailure(err as Error)
    }
  }

  private onDone(ev: Captured) {
    const waiting = this.rows[this.cursor]
    if (waiting?.on.event && waiting.turn === ev.turn && waiting.on.event !== 'done')
      this.fail(`row ${waiting.id}: the run ended without a "${waiting.on.event}" event`)
    const runId = ev.data.run_id
    const n = this.traces.length + 1
    this.pendingTrace = (async () => {
      const response = await this.api.get(`/api/runs/${runId}`)
      expect(response.ok(), `GET /api/runs/${runId}`).toBe(true)
      const run = await response.json()
      this.traces.push(run)
      writeFileSync(join(this.outDir, `trace-turn-${n}.json`), JSON.stringify(run, null, 2))
      this.finishTurn()
    })()
  }

  /** The spec reached `name`: show its row (and follows), if the storyboard has one. */
  async step(name: string) {
    await this.idle()
    const row = this.rows[this.cursor]
    if (row?.on.step === name) {
      for (const r of this.take()) await this.show(r)
      return
    }
    const later = this.rows.findIndex((r) => r.on.step === name)
    if (later > this.cursor) this.fail(`step "${name}" reached before row ${row?.id} (${JSON.stringify(row?.on)})`)
  }

  finish() {
    this.check()
    if (this.cursor !== this.rows.length) this.fail(`rows not shown: ${this.rows.slice(this.cursor).map((r) => r.id).join(', ')}`)
  }
}

function invariants(): string[] {
  const text = readFileSync(join(ROOT, 'CLAUDE.md'), 'utf8')
  const section = text.split(/^## Invariants.*$/m)[1]?.split(/^## /m)[0] ?? ''
  const items = [...section.matchAll(/^\d+\.\s+\*\*(.+?)\*\*/gm)].map((m) => m[1].replace(/\.$/, ''))
  if (items.length !== 8) throw new Error(`CLAUDE.md: expected 8 invariants, found ${items.length}`)
  return items
}

// ---------------------------------------------------------------- shared setup

async function guard(api: APIRequestContext, provider: string) {
  const hint = 'Start the app with start.cmd, answer n (no Groq), then d (demo), and run this again.'
  let health: any
  try {
    const response = await api.get('/api/health', { timeout: 5_000 })
    health = await response.json()
  } catch {
    throw new Error(`The app is not running at ${test.info().project.use.baseURL}. ${hint}`)
  }
  if (health.llm_provider !== provider)
    throw new Error(`The app runs provider "${health.llm_provider}", this take needs "${provider}". ${hint}`)
  return health
}

async function openStage(browser: import('@playwright/test').Browser, baseURL: string, outDir: string, onEvent?: (e: any) => Promise<void>) {
  const context = await browser.newContext({ baseURL, viewport: STAGE, recordVideo: { dir: join(outDir, 'raw'), size: STAGE } })
  await context.route('**/__video/*', (route) => {
    const name = new URL(route.request().url()).pathname.split('/').pop()!
    if (!['stage.html', 'stage.js'].includes(name)) return route.fulfill({ status: 404 })
    return route.fulfill({ path: join(HERE, name), contentType: name.endsWith('.js') ? 'text/javascript' : 'text/html' })
  })
  await context.addInitScript(CAPTURE)
  await context.exposeBinding('__videoEvent', async (_source, event) => (onEvent ? onEvent(event) : undefined))
  const t0 = Date.now()
  const page = await context.newPage()
  await page.goto('/__video/stage.html')
  const app = page.frameLocator('#app')
  return { context, page, app, t0 }
}

async function loadApp(page: Page) {
  await page.evaluate(() => (window as any).stage.loadApp())
  await expect(page.frameLocator('#app').getByRole('heading', { name: 'Create Design' })).toBeVisible()
}

async function assertNoPaths(page: Page, where: string) {
  const text: string = await page.evaluate(() => (window as any).stage.appText())
  const hit = text.match(PATH_RE)
  if (hit) throw new Error(`${where}: a local path is visible in the app ("${hit[0]}")`)
}

// ---------------------------------------------------------------- the takes

test('smoke: the stage at 1920x1080 @smoke', async ({ browser, baseURL, request }) => {
  const outDir = join(HERE, 'out', 'smoke')
  mkdirSync(outDir, { recursive: true })
  const health = await guard(request, storyboard.provider)
  const { context, page } = await openStage(browser, baseURL!, outDir)
  await page.evaluate((b) => (window as any).stage.init(b), { banner: storyboard.banner, provider: `/api/health: ${health.llm_provider}` })
  await loadApp(page)
  const row = storyboard.rows.find((r) => r.id === '1.3') as Row
  const callouts = row.callouts!.map(([f, s]) => resolveLine(f, s))
  await page.evaluate((c) => (window as any).stage.show(c), {
    id: row.id, subtitle: row.subtitle, layer: row.layer, callouts,
    payload: { label: 'GET /api/health', note: 'captured', value: health },
  })
  const box = async (sel: string) => page.locator(sel).boundingBox()
  expect(await box('#app')).toEqual({ x: 0, y: 0, width: 1280, height: 960 })
  expect(await box('#panel')).toEqual({ x: 1280, y: 0, width: 640, height: 960 })
  expect(await box('#subs')).toEqual({ x: 0, y: 960, width: 1920, height: 120 })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > 1920 || document.documentElement.scrollHeight > 1080)
  expect(overflow, 'the stage scrolls').toBe(false)
  await sleep(5_000)
  await page.evaluate(() => (window as any).stage.slide('map'))
  await sleep(4_000)
  await page.screenshot({ path: join(outDir, 'stage.png') })
  const video = page.video()
  await context.close()
  await video?.saveAs(join(outDir, 'smoke.webm'))
})

test('demo take @demo', async ({ browser, baseURL, request }) => {
  test.setTimeout(30 * 60_000)
  const outDir = join(HERE, 'out', 'demo')
  mkdirSync(outDir, { recursive: true })
  const health = await guard(request, storyboard.provider)

  let conductor!: Conductor
  const { context, page, app, t0 } = await openStage(browser, baseURL!, outDir, (e) => conductor.onEvent(e))
  conductor = new Conductor(page, context.request, outDir)
  conductor.t0 = t0
  const S = storyboard.sentences
  const until = <T>(p: Promise<T>) => conductor.until(p)

  try {
    await page.evaluate((b) => (window as any).stage.init(b), { banner: storyboard.banner, provider: `provider ${health.llm_provider} · model rules` })

    // Scene 0: slides
    for (const name of ['title', 'map', 'invariants']) await conductor.step(name)

    const ask = async (key: keyof typeof S) => {
      const input = app.getByLabel(/describe your design/i)
      await input.click()
      conductor.beginTurn(key, S[key])
      await input.pressSequentially(S[key], { delay: TYPE_DELAY_MS })
      await conductor.step(`typed:${key}`)
      await app.getByRole('button', { name: 'Send' }).click()
      await conductor.until(conductor.waitTurn(), TURN_TIMEOUT_MS, `turn "${key}"`)
    }

    // Scene 1: a rule question
    await loadApp(page)
    await page.evaluate(() => (window as any).stage.hideSlide())
    await ask('question')
    const citation = app.getByRole('button', { name: /^\[07-faq#revision-i\]$/ }).last()
    await expect(citation).toBeVisible()
    await conductor.step('citation')
    await citation.click()
    await expect(app.getByRole('dialog')).toBeVisible()
    await sleep(2500)
    await page.keyboard.press('Escape')
    await app.getByRole('button', { name: 'Agent steps' }).click()
    await expect(app.getByRole('dialog')).toBeVisible()
    await conductor.step('drawer')
    await assertNoPaths(page, 'Agent steps drawer')
    await page.keyboard.press('Escape')

    // Scene 2: fill the form from one sentence, then the same with revision I
    await loadApp(page)
    await ask('fill')
    await expect(app.getByRole('region', { name: 'Create this design?' }).last()).toBeVisible()
    await expect(app.getByLabel('Design number')).toHaveValue('HL-HW-26-0003')
    await sleep(1500)
    await ask('fill_wrong')
    await expect(app.getByText(/never used/).first()).toBeVisible()

    // Scene 3: reserve a SAP number (a fresh page: no form values from scene 2)
    await loadApp(page)
    await ask('reserve')
    const reserveCard = app.getByRole('region', { name: 'Reserve a new SAP number?' }).last()
    await expect(reserveCard).toBeVisible()

    // Scene 4: confirm, then create the design from the form
    await reserveCard.getByRole('button', { name: 'Confirm' }).click()
    await expect(app.getByLabel('Design number')).toHaveValue(/^HL-HW-\d{2}-\d{4}$/, { timeout: 60_000 })
    await until(conductor.idle())
    await expect(app.getByText(/Fill in first/)).toHaveCount(0)
    const description = app.getByLabel(/^Description/)
    await description.click()
    await description.pressSequentially(S.description, { delay: TYPE_DELAY_MS })
    await sleep(800)
    await app.getByRole('button', { name: 'Create design', exact: true }).click()
    const createCard = app.getByRole('region', { name: 'Create this design?' }).last()
    await expect(createCard).toBeVisible()
    await until(conductor.idle())
    await createCard.getByRole('button', { name: 'Confirm' }).click()
    const preview = app.getByRole('dialog').getByRole('img')
    await expect.poll(() => preview.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0), { timeout: 180_000 }).toBe(true)
    await until(conductor.idle())
    await assertNoPaths(page, 'preview dialog')
    await sleep(2500)
    const openKicad = process.env.VIDEO_OPEN_KICAD !== '0'
    if (openKicad) {
      await app.getByRole('button', { name: 'Open in KiCad' }).click()
      await expect(app.getByText(/schematic editor is opening with the design/)).toBeVisible({ timeout: 30_000 })
    }
    await conductor.step('open_kicad')
    if (openKicad) {
      // The KiCad ending (decision 0030): the schematic editor the click opened, recorded on
      // the desktop; compose.mjs puts it here in place of these browser frames.
      const created = conductor.lastConfirm('create_design')
      const stem = `${created.design_number}_${created.revision}`
      await conductor.until(captureEditor({ stem, outDir, now: () => conductor.now() }), 120_000, 'KiCad')
    }

    // Scenes 5-7: the trace of the reserve run, the comparison, the end card
    for (const name of ['trace', 'compare', 'close']) await conductor.step(name)
    await sleep(1500)
    conductor.finish()
  } finally {
    writeFileSync(join(outDir, 'events.json'), JSON.stringify(conductor.events, null, 2))
    writeFileSync(join(outDir, 'shown.json'), JSON.stringify(conductor.shown, null, 2))
    const video = page.video()
    await context.close()
    if (video) {
      await video.saveAs(join(outDir, 'take.webm.part'))
      renameSync(join(outDir, 'take.webm.part'), join(outDir, 'take.webm'))
    }
  }
})
