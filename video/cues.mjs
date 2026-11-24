/**
 * After a take: shown rows -> cues.json (start/end per subtitle), and the checks that make
 * the video trustworthy (decision 0028):
 *   - strict mode (the demo, deterministic): every storyboard row was shown, once, in order;
 *     flexible mode (a real model): every row shown is a storyboard row or a generic one, and
 *     the rows that never matched are listed;
 *   - every payload on screen equals the captured data it names (events.json,
 *     trace-turn-N.json, or a fresh run of introspect.py);
 *   - no payload shows a local path.
 *
 *   node cues.mjs out/demo            build cues.json and check
 *   node cues.mjs out/demo --verify   check only
 */
import { execFileSync } from 'node:child_process'
import { isDeepStrictEqual } from 'node:util'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
const PYTHON =
  process.env.VIDEO_PYTHON ||
  join(ROOT, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
// Checked on string values, not JSON text: there a newline after "directory:" reads "y:\n".
const PATH_RE = /(?<![A-Za-z])[A-Za-z]:\\[^\s\\]|\\Users\\|\/home\/|MyData/
const hasLocalPath = (value) =>
  typeof value === 'string'
    ? PATH_RE.test(value)
    : value !== null && typeof value === 'object'
      ? Object.values(value).some(hasLocalPath)
      : false
const TAIL_MS = 1500 // the last subtitle stays this long after its hold

const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'))

function pick(value, path) {
  if (!path) return value
  for (const part of path.split('.')) value = value?.[/^\d+$/.test(part) ? Number(part) : part]
  return value
}

export function buildCues(shown) {
  return shown.map((s, i) => ({
    id: s.id,
    start_ms: s.t_ms,
    end_ms: i + 1 < shown.length ? shown[i + 1].t_ms : s.t_ms + s.hold_ms + TAIL_MS,
    subtitle: s.subtitle,
  }))
}

function verify(dir, storyboard, shown, mode) {
  const problems = []
  const notes = []
  const expected = storyboard.rows.map((r) => r.id)
  const got = shown.map((s) => s.id)
  if (mode === 'flexible') {
    const unknown = got.filter((id) => !expected.includes(id) && !/^g\d+$/.test(id))
    if (unknown.length) problems.push(`rows not in the storyboard: ${unknown.join(', ')}`)
    const missing = expected.filter((id) => !got.includes(id))
    if (missing.length) notes.push(`never matched (not in the video): ${missing.join(', ')}`)
    const generic = got.filter((id) => /^g\d+$/.test(id))
    if (generic.length) notes.push(`generic rows for unforeseen events: ${generic.length}`)
  } else if (!isDeepStrictEqual(got, expected)) {
    const missing = expected.filter((id) => !got.includes(id))
    problems.push(`rows: expected ${expected.length} in storyboard order, got ${got.length}` + (missing.length ? `; missing ${missing.join(', ')}` : '; order differs'))
  }
  const events = readJson(join(dir, 'events.json'))
  const traces = {}
  let checked = 0
  for (const s of shown) {
    if (!s.source) continue
    const { from } = s.source
    let truth
    if (from === 'event' || from === 'request' || from === 'confirm' || from === 'action') {
      const ev = events[s.source.index]
      if (!ev || (from !== 'event' && ev.type !== from)) problems.push(`${s.id}: captured ${from} #${s.source.index} is missing`)
      truth = pick(ev?.data, s.source.pick)
    } else if (from === 'trace') {
      traces[s.source.turn] ??= readJson(join(dir, `trace-turn-${s.source.turn}.json`))
      truth = pick(traces[s.source.turn], s.source.pick)
    } else if (from.startsWith('introspect:')) {
      truth = JSON.parse(execFileSync(PYTHON, [join(HERE, 'introspect.py'), ...s.source.args], { encoding: 'utf8' }))
    }
    checked++
    if (!isDeepStrictEqual(s.payload, truth)) problems.push(`${s.id}: the payload on screen differs from the captured ${from}`)
    if (hasLocalPath(s.payload)) problems.push(`${s.id}: the payload shows a local path`)
  }
  // The FTS ranking shown (introspect) must be the order the tool returned in the take.
  for (const s of shown.filter((x) => x.source?.from === 'introspect:fts')) {
    const result = events.find((e) => e.type === 'tool_result' && e.data?.name === 'search_design_manual' && e.data?.auto)
    const returned = (result?.data?.result?.passages ?? []).map((p) => p.source)
    const ranked = s.payload.ranked.map((r) => r.source).slice(0, returned.length)
    if (!returned.length || !isDeepStrictEqual(ranked, returned)) problems.push(`${s.id}: FTS ranking ${ranked} differs from the tool result ${returned}`)
  }
  return { problems, checked, notes }
}

const [dirArg, flag] = process.argv.slice(2)
if (!dirArg) {
  console.error('usage: node cues.mjs out/<video> [--verify]')
  process.exit(2)
}
const dir = resolve(HERE, dirArg)
// take.json (written by the take) names its storyboard and mode; older takes: the demo's.
const take = existsSync(join(dir, 'take.json')) ? readJson(join(dir, 'take.json')) : {}
const storyboard = readJson(join(HERE, take.storyboard ?? 'storyboard.json'))
const mode = take.mode ?? 'strict'
const shown = readJson(join(dir, 'shown.json'))
if (flag !== '--verify') {
  writeFileSync(join(dir, 'cues.json'), JSON.stringify(buildCues(shown), null, 2))
  console.log(`cues.json: ${shown.length} cues`)
}
const { problems, checked, notes } = verify(dir, storyboard, shown, mode)
for (const note of notes) console.log(`note: ${note}`)
if (problems.length) {
  console.error(problems.map((p) => `FAIL ${p}`).join('\n'))
  process.exit(1)
}
const order = mode === 'flexible' ? 'shown (flexible mode)' : 'in storyboard order'
console.log(`ok: ${shown.length} rows ${order}; ${checked} payloads equal the capture; no local paths`)
