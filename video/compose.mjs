/**
 * take.webm (+ kicad.mp4) -> video.mp4 (H.264) and subtitles.en.srt.
 *
 * With a KiCad ending (kicad.json from the take, decision 0030), the browser frames recorded
 * while KiCad was on the desktop are replaced by the KiCad clip: scaled into the stage's
 * 1920x960 area, with a "screen recording" label, the zoom on the title block from
 * cues-kicad.json (a crop of the same frames, labelled "zoomed in"), and its subtitles drawn in
 * the stage's subtitle bar. The take's subtitles are burned into the stage already; the
 * .srt is for players and search.
 *
 *   node compose.mjs out/demo
 */
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const W = 1920
const STAGE_H = 960
const H = 1080
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

/** The take's cues with the KiCad clip spliced in at [a, b) of the take (ms). */
export function spliceCues(cues, kicadCues, a, b, clipMs) {
  const shift = clipMs - (b - a)
  const before = cues.filter((c) => c.start_ms < a).map((c) => ({ ...c, end_ms: Math.min(c.end_ms, a) }))
  const inserted = kicadCues.map((k) => ({ id: k.id, start_ms: a + k.start * 1000, end_ms: a + Math.min(k.end * 1000, clipMs), subtitle: k.subtitle }))
  const after = cues.filter((c) => c.start_ms >= b).map((c) => ({ ...c, start_ms: c.start_ms + shift, end_ms: c.end_ms + shift }))
  return [...before, ...inserted, ...after]
}

/**
 * The filter for one piece of the KiCad clip that starts `from` seconds into it: optionally
 * a crop (the cut to the title block), scaled into the stage's 1920x960 area, the "screen
 * recording" label, and the subtitles of that time in the stage's subtitle bar.
 * (Not zoompan: on video input it multiplies the frames, 16 s became 8,192 s.)
 */
function kicadFilter(spec, textFiles, { from, crop }) {
  const text = (file, size, color, xy, enable) =>
    `drawtext=fontfile='${FONT}':textfile='${file}':fontsize=${size}:fontcolor=${color}:${xy}${enable ? `:enable='${enable}'` : ''}`
  const parts = [
    ...(crop ? [`crop=${crop.w}:${crop.h}:${crop.x}:${crop.y}`] : []),
    `scale=${W}:${STAGE_H}:force_original_aspect_ratio=decrease:flags=lanczos`,
    `pad=${W}:${STAGE_H}:(ow-iw)/2:(oh-ih)/2:color=0x0f1720`,
    `pad=${W}:${H}:0:0:color=0x0a1016`,
    text(textFiles.label, 22, 'white@0.9', 'x=24:y=20:box=1:boxcolor=0x0f1720@0.75:boxborderw=10'),
    ...(crop ? [text(textFiles.zoom, 22, '0x39b3a6', 'x=24:y=66:box=1:boxcolor=0x0f1720@0.75:boxborderw=10')] : []),
    // drawtext's t is the piece's own time
    ...spec.cues.map((c, i) =>
      text(textFiles.cues[i], 30, 'white', `x=(w-text_w)/2:y=${STAGE_H}+(${H - STAGE_H}-text_h)/2`, `between(t+${from},${c.start},${c.end})`),
    ),
    'fps=30', 'format=yuv420p', 'setsar=1',
  ]
  return parts.join(',')
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

function main() {
  const dirArg = process.argv[2]
  if (!dirArg) {
    console.error('usage: node compose.mjs out/<video>')
    process.exit(2)
  }
  const dir = resolve(HERE, dirArg)
  if (!existsSync(join(dir, 'take.webm'))) {
    console.error(`${join(dir, 'take.webm')} not found: record the take first`)
    process.exit(1)
  }
  let cues = JSON.parse(readFileSync(join(dir, 'cues.json'), 'utf8'))
  const kicadInfo = existsSync(join(dir, 'kicad.json')) && existsSync(join(dir, 'kicad.mp4'))
    ? JSON.parse(readFileSync(join(dir, 'kicad.json'), 'utf8'))
    : null

  if (!kicadInfo) {
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', 'take.webm', ...encodeArgs('video.mp4')], { cwd: dir, stdio: 'inherit' })
  } else {
    const spec = JSON.parse(readFileSync(join(HERE, 'cues-kicad.json'), 'utf8'))
    // Plain-text files for drawtext: no escaping of ':' or ',' in the subtitles.
    const textFiles = { label: 'kicad-label.txt', zoom: 'kicad-zoom.txt', cues: spec.cues.map((_, i) => `kicad-cue-${i}.txt`) }
    writeFileSync(join(dir, textFiles.label), spec.label)
    writeFileSync(join(dir, textFiles.zoom), spec.zoom.label)
    spec.cues.forEach((c, i) => writeFileSync(join(dir, textFiles.cues[i]), c.subtitle))
    const a = kicadInfo.start_ms / 1000
    const b = kicadInfo.end_ms / 1000
    // Three pieces encoded alike, then joined without re-encoding. (One filter graph that
    // reads take.webm twice has to hold minutes of raw frames until the concat needs them.)
    const same = ['-vf', 'fps=30,format=yuv420p,setsar=1']
    const ffmpeg = (args) => execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...args], { cwd: dir, stdio: 'inherit' })
    ffmpeg(['-i', 'take.webm', '-t', String(a), ...same, ...encodeArgs('part-1.mp4')])
    // The KiCad clip in two pieces: the whole sheet, then a cut to the title block.
    const zoomAt = spec.zoom.start
    const crop = zoomRect(kicadInfo.area, spec.zoom)
    ffmpeg(['-i', 'kicad.mp4', '-t', String(zoomAt), '-vf', kicadFilter(spec, textFiles, { from: 0 }), ...encodeArgs('part-2.mp4')])
    ffmpeg(['-ss', String(zoomAt), '-i', 'kicad.mp4', '-vf', kicadFilter(spec, textFiles, { from: zoomAt, crop }), ...encodeArgs('part-3.mp4')])
    ffmpeg(['-ss', String(b), '-i', 'take.webm', ...same, ...encodeArgs('part-4.mp4')])
    const parts = ['part-1.mp4', 'part-2.mp4', 'part-3.mp4', 'part-4.mp4']
    writeFileSync(join(dir, 'parts.txt'), parts.map((p) => `file '${p}'`).join('\n'))
    ffmpeg(['-f', 'concat', '-safe', '0', '-i', 'parts.txt', '-c', 'copy', '-movflags', '+faststart', 'video.mp4'])
    const clipMs = (duration(join(dir, 'part-2.mp4')) + duration(join(dir, 'part-3.mp4'))) * 1000
    cues = spliceCues(cues, spec.cues, kicadInfo.start_ms, kicadInfo.end_ms, clipMs)
  }
  writeFileSync(join(dir, 'subtitles.en.srt'), srt(cues))
  console.log(`${join(dir, 'video.mp4')} (${duration(join(dir, 'video.mp4')).toFixed(1)} s)\n${join(dir, 'subtitles.en.srt')} (${cues.length} cues)`)
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main()
