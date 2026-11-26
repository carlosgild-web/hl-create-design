/**
 * The KiCad ending (decisions 0028, 0030 and 0036): after the take clicks "Open in KiCad",
 * the app starts KiCad's schematic editor on this PC; after "Open PCB", its PCB editor.
 * Playwright cannot see a desktop window, so this module waits for it, maximizes it, and
 * records its screen with ffmpeg `gdigrab`. compose.mjs puts each clip in the take where
 * its click happened.
 *
 * Windows only (KiCad is a desktop program on the user's machine). PowerShell and ffmpeg,
 * no extra dependency. The capture is the monitor's working area: no taskbar. The window
 * title is "<design>_<rev> — Schematic Editor" or "... — PCB Editor" (no path), checked
 * when it is found.
 */
import { execFile, execFileSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'
import { join } from 'node:path'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function powershell(script) {
  return execFileSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', script], {
    encoding: 'utf8',
  }).trim()
}

// Physical pixels (the process is made DPI-aware before asking), so they match gdigrab.
const WIN32 = String.raw`
Add-Type @"
using System; using System.Runtime.InteropServices;
public class VideoWin {
  [StructLayout(LayoutKind.Sequential)] public struct R { public int L, T, Ri, B; }
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
"@
[VideoWin]::SetProcessDPIAware() | Out-Null
Add-Type -AssemblyName System.Windows.Forms
`

/** The two editors a take records: the process, the files it writes, its name in errors. */
export const EDITORS = {
  schematic: { process: 'eeschema', clip: 'kicad', name: "KiCad's schematic editor" },
  pcb: { process: 'pcbnew', clip: 'kicad-pcb', name: "KiCad's PCB editor" },
}

/** The editor's window for `stem` (e.g. HL-HW-26-0049_A), once it has loaded. */
export async function waitForEditor(stem, editor = 'schematic', timeoutMs = 60_000) {
  const { process, name } = EDITORS[editor]
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const out = powershell(
      `Get-Process ${process} -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '${stem}*' } | Select-Object -First 1 | ForEach-Object { "$($_.Id)|$($_.MainWindowTitle)" }`,
    )
    if (out) {
      const [pid, title] = out.split('|')
      return { pid: Number(pid), title }
    }
    await sleep(500)
  }
  throw new Error(`${name} did not open ${stem} within ${timeoutMs / 1000} s`)
}

/** Maximize the window, bring it to the front, and return its monitor's working area. */
export function maximize(pid) {
  const out = powershell(`${WIN32}
$h = (Get-Process -Id ${pid}).MainWindowHandle
[VideoWin]::ShowWindow($h, 3) | Out-Null
[VideoWin]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 700
$a = [System.Windows.Forms.Screen]::FromHandle($h).WorkingArea
"$($a.X)|$($a.Y)|$($a.Width)|$($a.Height)"`)
  const [x, y, width, height] = out.split('|').map(Number)
  return { x, y, width: width - (width % 2), height: height - (height % 2) }
}

/** Record `area` of the desktop for `seconds` into `file` (H.264). */
export function record(area, seconds, file) {
  return new Promise((resolve, reject) => {
    execFile(
      'ffmpeg',
      [
        '-y', '-loglevel', 'error',
        '-f', 'gdigrab', '-framerate', '30', '-draw_mouse', '0',
        '-offset_x', String(area.x), '-offset_y', String(area.y),
        '-video_size', `${area.width}x${area.height}`, '-i', 'desktop',
        '-t', String(seconds), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
        '-pix_fmt', 'yuv420p', file,
      ],
      (err) => (err ? reject(err) : resolve()),
    )
  })
}

/** Close the editor the take opened (gracefully: nothing was changed, nothing to save). */
export function close(pid) {
  powershell(`$p = Get-Process -Id ${pid} -ErrorAction SilentlyContinue; if ($p) { $p.CloseMainWindow() | Out-Null }`)
}

/**
 * One KiCad clip: wait for the editor's window, maximize it, record it. Writes
 * `kicad.mp4` + `kicad.json` (schematic) or `kicad-pcb.mp4` + `kicad-pcb.json` (PCB): when
 * it started and ended on the take's clock, the title, the area.
 */
export async function captureEditor({ stem, outDir, now, seconds = 16, editor = 'schematic' }) {
  const window = await waitForEditor(stem, editor)
  if (/[A-Za-z]:\\|\\Users\\/.test(window.title)) throw new Error(`the KiCad title shows a path: ${window.title}`)
  const area = maximize(window.pid)
  await sleep(editor === 'pcb' ? 2500 : 1500) // KiCad redraws the sheet for the new size
  const { clip } = EDITORS[editor]
  const start_ms = now()
  await record(area, seconds, join(outDir, `${clip}.mp4`))
  const end_ms = now()
  close(window.pid)
  const info = { editor, start_ms, end_ms, seconds, title: window.title, area }
  writeFileSync(join(outDir, `${clip}.json`), JSON.stringify(info, null, 2))
  return info
}
