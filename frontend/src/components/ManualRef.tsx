import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { getManualPassage } from '@/api/client'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { InlineMarkdown, ManualText } from '@/components/ManualText'
import { useI18n } from '@/i18n'
import { normalizeRefs } from '@/lib/issues'

const REF = /\[([\w-]+#[\w-]+)\]/g

/** `[02-revisions#skipped-letters]` as a button that opens that manual section (decision 0026). */
export function ManualRef({ source }: { source: string }) {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const passage = useQuery({
    queryKey: ['manual', lang, source],
    queryFn: () => getManualPassage(lang, source),
    enabled: open,
    staleTime: Infinity,
    retry: false,
  })
  return (
    <>
      <button
        type="button"
        className="text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground"
        // The visible "[ref]" is the name; the hint is a tooltip, so form labels stay unique.
        title={t('manual.open', { source })}
        onClick={() => setOpen(true)}
      >
        [{source}]
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="w-[min(95vw,40rem)]" closeLabel={t('preview.close')}>
          <DialogHeader>
            <DialogTitle>{passage.data?.heading ?? source}</DialogTitle>
            <DialogDescription className="tabular-nums">
              {t('manual.source', { document: passage.data?.document ?? source.split('#')[0], source })}
            </DialogDescription>
          </DialogHeader>
          <div className="overflow-y-auto text-sm leading-relaxed">
            {passage.isPending ? t('manual.loading') : passage.isError ? t('manual.missing') : <ManualText text={passage.data.text} />}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

/** Free text (an assistant answer) with each `[ref]` it cites as a `ManualRef`. */
export function WithRefs({ text }: { text: string }) {
  const clean = normalizeRefs(text)
  const parts: (string | { source: string })[] = []
  let last = 0
  for (const match of clean.matchAll(REF)) {
    parts.push(clean.slice(last, match.index), { source: match[1] })
    last = (match.index ?? 0) + match[0].length
  }
  parts.push(clean.slice(last))
  return (
    <>
      {parts.map((part, i) => (typeof part === 'string' ? <InlineMarkdown key={i} text={part} /> : <ManualRef key={i} source={part.source} />))}
    </>
  )
}
