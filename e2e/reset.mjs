// Empties a folder before a server starts, so every run begins from a clean demo.
import { rmSync, mkdirSync } from 'node:fs'

for (const dir of process.argv.slice(2)) {
  rmSync(dir, { recursive: true, force: true })
  mkdirSync(dir, { recursive: true })
}
