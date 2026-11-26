/**
 * take.webm (+ kicad.mp4, kicad-pcb.mp4) -> video.mp4 (H.264) and subtitles.en.srt.
 *
 *   node compose.mjs out/demo
 *   node compose.mjs out/dahl --cut-gaps --readme
 *
 * The video is a list of pieces, encoded apart and joined without re-encoding:
 * - take pieces;
 * - with a KiCad ending (kicad.json, decision 0030; kicad-pcb.json, decision 0036), each
 *   KiCad clip in place of the browser frames recorded while that editor was on the desktop.
 *   It is scaled into the stage's 1920x960 area, with a "screen recording" label, then cut
 *   to a crop of the same frames around the title block (labelled "zoomed in"), and its
 *   subtitles go in the stage's subtitle bar;
 * - with --cut-gaps (a real model), every wait over 3 s inside a chat turn, where nothing
 *   changed on screen, is kept for 1 s with a label that says how long it really was. A wait
 *   is never removed without that label.
 *
 * --readme also writes video-readme.mp4 (1280x720, two-pass, under 10 MB for GitHub's
 * inline player) and poster.png. The take's subtitles are burned into the stage already;
 * the .srt is for players and search.
 */
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const W = 1920
const STAGE_H = 960
const H = 1080
const GAP_S = 3 // a wait longer than this is shortened
const KEEP_S = 1 // to this, with its label
const README_MB = 9.5 // GitHub plays inline up to 10 MB on free accounts
// drawtext needs a font file; Segoe UI is the stage's font on Windows.
const FONT = (process.env.VIDEO_FONT || 'C:/Windows/Fonts/segoeui.ttf').replace(/:/g, '\\:')

function stamp(ms) {
  const t = Math.max(0, Math.round(ms))
  const pad = (n, w = 2) => String(n).padStart(w, '0')
  return `${pad(Math.floor(t / 3_600_000))}:${pad(Math.floor(t / 60_000) % 60)}:${pad(Math.floor(t / 1000) % 60)},${pad(t % 1000, 3)}`
}

export function srt(cues) {
  return cues.map((c, i) => `${i + 1}\n${stamp(c.start_ms)} --> ${stamp(c.end_ms)}\n${c.subtitle}\n`).join('\n')
}

function duration(file) {
  const out = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file], { encoding: 'utf8' })
  return Number(out.trim())
}

/**
 * The waits to shorten, in seconds of the take: inside each chat turn (from the request to
 * `done`), the spans where no row was on screen and no event changed the app for over
 * GAP_S. Those are model calls and SAP or KiCad work seen as "Thinking…".
 */
export function findGaps(events, shown) {
  const busy = [
    ...shown.map((s) => [s.t_ms, s.t_ms + s.hold_ms]),
    ...events.map((e) => [e.t_ms, e.t_ms + 800]), // the app renders what came
  ].sort((a, b) => a[0] - b[0])
  const gaps = []
  for (const req of events.filter((e) => e.type === 'request')) {
    const done = events.find((e) => e.type === 'done' && e.t_ms > req.t_ms)
    if (!done) continue
    let at = req.t_ms
    for (const [from, to] of busy) {
      if (to <= at || from >= done.t_ms) continue
      if (from - at > GAP_S * 1000) gaps.push({ from: at / 1000, to: from / 1000 })
      at = Math.max(at, to)
    }
  }
  return gaps
}

/** The KiCad clips a take recorded, in the order the editors opened (schematic, then PCB). */
export const KICAD_CLIPS = [
  { editor: 'schematic', clip: 'kicad' },
  { editor: 'pcb', clip: 'kicad-pcb' },
]

/**
 * The pieces of the final video, in order. Take pieces are [from, to) of the take; each
 * KiCad clip (`{ editor, start_ms, end_ms }`, from its .json) replaces the take's frames
 * recorded while it ran.
 */
export function planPieces(takeS, gaps, clips = []) {
  const cuts = [...gaps.map((g) => ({ kind: 'gap', ...g }))]
  for (const c of clips) cuts.push({ kind: 'kicad', editor: c.editor, from: c.start_ms / 1000, to: c.end_ms / 1000 })
  cuts.sort((a, b) => a.from - b.from)
  const pieces = []
  let pos = 0
  for (const cut of cuts) {
    if (cut.from < pos) continue // overlaps an earlier cut
    if (cut.from > pos) pieces.push({ src: 'take', from: pos, to: cut.from })
    if (cut.kind === 'gap') {
      const waited = cut.to - cut.from
      pieces.push({ src: 'take', from: cut.from, to: cut.from + KEEP_S, label: `waiting for the model: ${waited.toFixed(0)} s, shortened to ${KEEP_S} s` })
    } else {
      pieces.push({ src: 'kicad', editor: cut.editor, from: cut.from, to: cut.to })
    }
    pos = cut.to
  }
  if (pos < takeS) pieces.push({ src: 'take', from: pos, to: takeS })
  return pieces
}

/** A take time (ms) in the final video, given each piece's length there (s). */
function mapper(pieces, lengths) {
  return (ms) => {
    const t = ms / 1000
    let out = 0
    for (const [i, p] of pieces.entries()) {
      if (t < p.from) return out * 1000
      if (p.src === 'take' && t < p.to) return (out + (t - p.from)) * 1000
      if (p.src === 'kicad' && t < p.to) return out * 1000
      out += lengths[i]
    }
    return out * 1000
  }
}

/**
 * The filter for one piece of the KiCad clip that starts `from` seconds into it: optionally
 * a crop (the cut to the title block), scaled into the stage's 1920x960 area, the "screen
 * recording" label, and the subtitles of that time in the stage's subtitle bar.
 * (Not zoompan: on video input it multiplies the frames, 16 s became 8,192 s.)
 */
function kicadFilter(spec, textFiles, { from, crop }) {
  const parts = [
    ...(crop ? [`crop=${crop.w}:${crop.h}:${crop.x}:${crop.y}`] : []),
    `scale=${W}:${STAGE_H}:force_original_aspect_ratio=decrease:flags=lanczos`,
    `pad=${W}:${STAGE_H}:(ow-iw)/2:(oh-ih)/2:color=0x0f1720`,
    `pad=${W}:${H}:0:0:color=0x0a1016`,
    // Bottom right of the stage: at the top left the label covered KiCad's menu bar.
    drawText(textFiles.label, 22, 'white@0.9', `x=w-text_w-24:y=${STAGE_H}-text_h-${crop ? 96 : 50}:box=1:boxcolor=0x0f1720@0.75:boxborderw=10`),
    ...(crop ? [drawText(textFiles.zoom, 22, '0x39b3a6', `x=w-text_w-24:y=${STAGE_H}-text_h-50:box=1:boxcolor=0x0f1720@0.75:boxborderw=10`)] : []),
    // drawtext's t is the piece's own time
    ...spec.cues.map((c, i) =>
      drawText(textFiles.cues[i], 30, 'white', `x=(w-text_w)/2:y=${STAGE_H}+(${H - STAGE_H}-text_h)/2`, `between(t+${from},${c.start},${c.end})`),
    ),
    'fps=30', 'format=yuv420p', 'setsar=1',
  ]
  return parts.join(',')
}

function drawText(file, size, color, xy, enable) {
  return `drawtext=fontfile='${FONT}':textfile='${file}':fontsize=${size}:fontcolor=${color}:${xy}${enable ? `:enable='${enable}'` : ''}`
}

/** The title block's rectangle in the capture: `factor` times narrower than the area, around
 * (cx, cy), inside the frame, in the stage's 2:1 aspect ratio. */
export function zoomRect(area, zoom) {
  const w = Math.round(area.width / zoom.factor / 2) * 2
  const h = Math.round(w / 4) * 2
  const clamp = (v, max) => Math.max(0, Math.min(max, Math.round(v)))
  return {
    w,
    h,
    x: clamp(zoom.cx * area.width - w / 2, area.width - w),
    y: clamp(zoom.cy * area.height - h / 2, area.height - h),
  }
}

function encodeArgs(out) {
  return ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', '-an', out]
}

/** The README copy: 1280x720, two-pass to stay under README_MB, and a poster frame. */
function readmeCopy(dir, ffmpeg, posterAt) {
  const seconds = duration(join(dir, 'video.mp4'))
  const kbps = Math.floor((README_MB * 8 * 1024) / seconds) - 16
  const common = ['-i', 'video.mp4', '-vf', 'scale=1280:720:flags=lanczos', '-c:v', 'libx264', '-preset', 'slow', '-b:v', `${kbps}k`, '-pix_fmt', 'yuv420p', '-an']
  const nul = process.platform === 'win32' ? 'NUL' : '/dev/null'
  ffmpeg([...common, '-pass', '1', '-passlogfile', 'readme-pass', '-f', 'mp4', nul])
  ffmpeg([...common, '-pass', '2', '-passlogfile', 'readme-pass', '-movflags', '+faststart', 'video-readme.mp4'])
  ffmpeg(['-ss', String(posterAt), '-i', 'video.mp4', '-frames:v', '1', '-update', '1', '-vf', 'scale=1280:720:flags=lanczos', 'poster.png'])
  const mb = statSync(join(dir, 'video-readme.mp4')).size / 1024 / 1024
  if (mb > 10) throw new Error(`video-readme.mp4 is ${mb.toFixed(1)} MB, over GitHub's 10 MB`)
  return mb
}

function main() {
  const [dirArg, ...flags] = process.argv.slice(2)
  if (!dirArg) {
    console.error('usage: node compose.mjs out/<video> [--cut-gaps] [--readme]')
    process.exit(2)
  }
  const dir = resolve(HERE, dirArg)
  if (!existsSync(join(dir, 'take.webm'))) {
    console.error(`${join(dir, 'take.webm')} not found: record the take first`)
    process.exit(1)
  }
  const read = (name) => JSON.parse(readFileSync(join(dir, name), 'utf8'))
  const ffmpeg = (args) => execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...args], { cwd: dir, stdio: 'inherit' })
  const cues = read('cues.json')
  const clips = KICAD_CLIPS.filter(({ clip }) => existsSync(join(dir, `${clip}.json`)) && existsSync(join(dir, `${clip}.mp4`))).map(
    ({ editor, clip }) => ({ ...read(`${clip}.json`), editor, clip }),
  )
  const gaps = flags.includes('--cut-gaps') ? findGaps(read('events.json'), read('shown.json')) : []
  const pieces = planPieces(duration(join(dir, 'take.webm')), gaps, clips)

  const kicadSpec = JSON.parse(readFileSync(join(HERE, 'cues-kicad.json'), 'utf8'))
  // Per clip: its zoom and cues, and plain-text files for drawtext (no escaping of ':' or ',').
  const specs = {}
  for (const { editor, clip } of clips) {
    const spec = kicadSpec.clips[editor]
    const textFiles = { label: `${clip}-label.txt`, zoom: `${clip}-zoom.txt`, cues: spec.cues.map((_, i) => `${clip}-cue-${i}.txt`) }
    writeFileSync(join(dir, textFiles.label), kicadSpec.label)
    writeFileSync(join(dir, textFiles.zoom), spec.zoom.label)
    spec.cues.forEach((c, i) => writeFileSync(join(dir, textFiles.cues[i]), c.subtitle))
    specs[editor] = { spec, textFiles, clip: clips.find((c) => c.editor === editor) }
  }

  const files = []
  const lengths = []
  let posterAt = 0
  for (const [i, p] of pieces.entries()) {
    if (p.src === 'take') {
      const file = `part-${String(files.length + 1).padStart(2, '0')}.mp4`
      let vf = 'fps=30,format=yuv420p,setsar=1'
      if (p.label) {
        writeFileSync(join(dir, `gap-${i}.txt`), p.label)
        vf += `,${drawText(`gap-${i}.txt`, 26, '0xe0a33a', 'x=(w-text_w)/2:y=24:box=1:boxcolor=0x0f1720@0.85:boxborderw=12')}`
      }
      ffmpeg(['-ss', String(p.from), '-i', 'take.webm', '-t', String(p.to - p.from), '-vf', vf, ...encodeArgs(file)])
      files.push(file)
      lengths.push(duration(join(dir, file)))
    } else {
      // A KiCad clip in two pieces: the whole sheet, then a cut to the title block.
      const { spec, textFiles, clip } = specs[p.editor]
      const source = `${clip.clip}.mp4`
      const zoomAt = spec.zoom.start
      const crop = zoomRect(clip.area, spec.zoom)
      const sheet = `part-${String(files.length + 1).padStart(2, '0')}.mp4`
      const block = `part-${String(files.length + 2).padStart(2, '0')}.mp4`
      ffmpeg(['-i', source, '-t', String(zoomAt), '-vf', kicadFilter(spec, textFiles, { from: 0 }), ...encodeArgs(sheet)])
      ffmpeg(['-ss', String(zoomAt), '-i', source, '-vf', kicadFilter(spec, textFiles, { from: zoomAt, crop }), ...encodeArgs(block)])
      files.push(sheet, block)
      // The poster: the schematic's title block, zoomed in.
      if (p.editor === 'schematic') posterAt = lengths.reduce((a, b) => a + b, 0) + zoomAt + 1.5
      lengths.push(duration(join(dir, sheet)) + duration(join(dir, block)))
    }
  }
  writeFileSync(join(dir, 'parts.txt'), files.map((f) => `file '${f}'`).join('\n'))
  ffmpeg(['-f', 'concat', '-safe', '0', '-i', 'parts.txt', '-c', 'copy', '-movflags', '+faststart', 'video.mp4'])

  // Subtitles on the final clock: the take's cues mapped, each KiCad clip's cues where it is.
  const map = mapper(pieces, lengths)
  const final = cues
    .map((c) => ({ ...c, start_ms: map(c.start_ms), end_ms: map(c.end_ms) }))
    .filter((c) => c.end_ms - c.start_ms > 300)
  for (const [k, p] of pieces.entries()) {
    if (p.src !== 'kicad') continue
    const at = lengths.slice(0, k).reduce((a, b) => a + b, 0) * 1000
    const { spec } = specs[p.editor]
    final.push(...spec.cues.map((c) => ({ id: c.id, start_ms: at + c.start * 1000, end_ms: at + Math.min(c.end * 1000, lengths[k] * 1000), subtitle: c.subtitle })))
  }
  final.sort((a, b) => a.start_ms - b.start_ms)
  writeFileSync(join(dir, 'subtitles.en.srt'), srt(final))
  writeFileSync(join(dir, 'pieces.json'), JSON.stringify(pieces.map((p, i) => ({ ...p, seconds: lengths[i] })), null, 2))

  const total = duration(join(dir, 'video.mp4'))
  console.log(`${join(dir, 'video.mp4')} (${total.toFixed(1)} s; ${gaps.length} waits shortened)\n${join(dir, 'subtitles.en.srt')} (${final.length} cues)`)
  if (flags.includes('--readme')) {
    const mb = readmeCopy(dir, ffmpeg, posterAt || total / 2)
    console.log(`${join(dir, 'video-readme.mp4')} (${mb.toFixed(1)} MB)\n${join(dir, 'poster.png')}`)
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main()
