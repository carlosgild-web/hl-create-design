import type { ReactNode } from 'react'

/**
 * A Design Manual passage as the manual writes it: the small Markdown subset its sections use
 * (paragraphs, `-` and `1.` lists, tables, **bold**, `code`, [links](file.md)). Links become
 * their text: the passage dialog shows one section, the cited file is not served. No raw HTML
 * is ever rendered, so a passage can't inject markup.
 */
export function ManualText({ text }: { text: string }) {
  return <div className="space-y-2">{blocks(text).map((block, i) => renderBlock(block, i))}</div>
}

type Block =
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; ordered: boolean; items: string[] }
  | { kind: 'table'; head: string[]; rows: string[][] }

const ITEM = /^\s*(?:([-*])|(\d+)\.)\s+(.*)$/

function blocks(text: string): Block[] {
  const out: Block[] = []
  for (const chunk of text.replace(/\r\n/g, '\n').split(/\n\s*\n/)) {
    const lines = chunk.split('\n').filter((line) => line.trim())
    if (!lines.length) continue
    if (lines.every((line) => line.trim().startsWith('|'))) {
      const cells = (line: string) =>
        line
          .trim()
          .replace(/^\||\|$/g, '')
          .split('|')
          .map((cell) => cell.trim())
      const [head, ...rest] = lines.map(cells)
      out.push({ kind: 'table', head, rows: rest.filter((row) => !row.every((cell) => /^:?-+:?$/.test(cell))) })
      continue
    }
    const first = ITEM.exec(lines[0])
    if (first) {
      const items: string[] = []
      for (const line of lines) {
        const item = ITEM.exec(line)
        if (item) items.push(item[3])
        else items[items.length - 1] += ` ${line.trim()}` // a wrapped line of the item above
      }
      out.push({ kind: 'list', ordered: !first[1], items })
      continue
    }
    out.push({ kind: 'paragraph', text: lines.map((line) => line.trim()).join(' ') })
  }
  return out
}

function renderBlock(block: Block, key: number) {
  if (block.kind === 'paragraph') return <p key={key}>{inline(block.text)}</p>
  if (block.kind === 'list') {
    const List = block.ordered ? 'ol' : 'ul'
    return (
      <List key={key} className={`space-y-1 pl-5 ${block.ordered ? 'list-decimal' : 'list-disc'}`}>
        {block.items.map((item, i) => (
          <li key={i}>{inline(item)}</li>
        ))}
      </List>
    )
  }
  return (
    <table key={key} className="w-full border-collapse text-left">
      <thead>
        <tr>
          {block.head.map((cell, i) => (
            <th key={i} className="border-b border-border px-2 py-1 font-medium">
              {inline(cell)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {block.rows.map((row, r) => (
          <tr key={r}>
            {row.map((cell, i) => (
              <td key={i} className="border-b border-border/60 px-2 py-1">
                {inline(cell)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Inline `code` and **bold** in a chat answer (models write them; shown raw they look broken). */
export function InlineMarkdown({ text }: { text: string }) {
  return <>{inline(text)}</>
}

const INLINE = /`([^`]+)`|\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)]*)\)/g

/** `code`, **bold** and [text](target) as text; everything else stays plain text. */
function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(INLINE)) {
    const index = match.index ?? 0
    if (index > last) parts.push(text.slice(last, index))
    const key = parts.length
    if (match[1] !== undefined)
      parts.push(
        <code key={key} className="rounded bg-muted px-1 font-mono text-[0.9em]">
          {match[1]}
        </code>,
      )
    else if (match[2] !== undefined) parts.push(<strong key={key}>{inline(match[2])}</strong>)
    else parts.push(match[3])
    last = index + match[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}
