/** `node --test` (npm run video:test): how compose.mjs cuts a take (decisions 0028, 0036). */
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { planPieces, srt, zoomRect } from './compose.mjs'

const schematic = { editor: 'schematic', start_ms: 100_000, end_ms: 116_000 }
const pcb = { editor: 'pcb', start_ms: 120_000, end_ms: 131_000 }

test('two KiCad clips replace the take where each editor was recorded', () => {
  assert.deepEqual(planPieces(140, [], [schematic, pcb]), [
    { src: 'take', from: 0, to: 100 },
    { src: 'kicad', editor: 'schematic', from: 100, to: 116 },
    { src: 'take', from: 116, to: 120 },
    { src: 'kicad', editor: 'pcb', from: 120, to: 131 },
    { src: 'take', from: 131, to: 140 },
  ])
})

test('a take without KiCad is one piece, and one clip still works', () => {
  assert.deepEqual(planPieces(50, []), [{ src: 'take', from: 0, to: 50 }])
  assert.equal(planPieces(140, [], [schematic]).filter((p) => p.src === 'kicad').length, 1)
})

test('model waits are shortened and labelled; the clips stay in order', () => {
  const pieces = planPieces(140, [{ from: 10, to: 20 }], [pcb, schematic])
  assert.deepEqual(pieces[1], { src: 'take', from: 10, to: 11, label: 'waiting for the model: 10 s, shortened to 1 s' })
  assert.deepEqual(
    pieces.filter((p) => p.src === 'kicad').map((p) => p.editor),
    ['schematic', 'pcb'],
  )
})

test('the zoom crop stays inside the capture, in the stage aspect ratio', () => {
  const crop = zoomRect({ width: 1920, height: 1020 }, { factor: 2.6, cx: 0.524, cy: 0.75 })
  assert.ok(crop.x >= 0 && crop.x + crop.w <= 1920)
  assert.ok(crop.y >= 0 && crop.y + crop.h <= 1020)
  assert.ok(Math.abs(crop.w / crop.h - 2) < 0.02)
})

test('srt numbers the cues and formats the times', () => {
  assert.equal(srt([{ start_ms: 1500, end_ms: 62_000, subtitle: 'Hi' }]), '1\n00:00:01,500 --> 00:01:02,000\nHi\n')
})
