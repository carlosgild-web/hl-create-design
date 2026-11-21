/**
 * take.webm -> video.mp4 (H.264, for players and GitHub) and subtitles.en.srt from cues.json.
 * The subtitles are also burned into the stage, so the .srt is for players and search.
 * Gap cutting is for the Ollama video (V4); the demo take has no model waits to cut.
 *
 *   node compose.mjs out/demo
 */
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))

function stamp(ms) {
  const t = Math.max(0, Math.round(ms))
  const pad = (n, w = 2) => String(n).padStart(w, '0')
  return `${pad(Math.floor(t / 3_600_000))}:${pad(Math.floor(t / 60_000) % 60)}:${pad(Math.floor(t / 1000) % 60)},${pad(t % 1000, 3)}`
}

export function srt(cues) {
  return cues.map((c, i) => `${i + 1}\n${stamp(c.start_ms)} --> ${stamp(c.end_ms)}\n${c.subtitle}\n`).join('\n')
}

const dirArg = process.argv[2]
if (!dirArg) {
  console.error('usage: node compose.mjs out/<video>')
  process.exit(2)
}
const dir = resolve(HERE, dirArg)
const take = join(dir, 'take.webm')
if (!existsSync(take)) {
  console.error(`${take} not found: record the take first`)
  process.exit(1)
}
const cues = JSON.parse(readFileSync(join(dir, 'cues.json'), 'utf8'))
writeFileSync(join(dir, 'subtitles.en.srt'), srt(cues))
execFileSync(
  'ffmpeg',
  ['-y', '-loglevel', 'error', '-i', take, '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', '-an', join(dir, 'video.mp4')],
  { stdio: 'inherit' },
)
console.log(`${join(dir, 'video.mp4')}\n${join(dir, 'subtitles.en.srt')} (${cues.length} cues)`)
