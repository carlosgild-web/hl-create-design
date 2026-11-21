import type { SapDesign } from '@/api/types'
import { issueText, type IssueLike } from '@/lib/issues'
import { Badge } from '@/components/ui/badge'
import { STATUS_STYLE } from '@/lib/status'
import { useI18n, type MessageKey } from '@/i18n'


/** Material numbers are shown without leading zeros (03-title-block). */
const shortMaterial = (m: string) => m.replace(/^0+/, '') || m

export function SapCard({ design, notes }: { design: SapDesign; notes: (IssueLike & { ref: string })[] }) {
  const { t, lang } = useI18n()
  const known = ['IN_WORK', 'RELEASED', 'BLOCKED', 'OBSOLETE'].includes(design.status)
  return (
    <section aria-label={t('sap.card')} className="rounded-lg border bg-card p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="tabular-nums font-medium">{design.design_number}</p>
        <Badge className={STATUS_STYLE[design.status]} variant="secondary">
          {known ? t(`status.${design.status}` as MessageKey) : design.status}
        </Badge>
      </div>
      <p className="text-muted-foreground">{design.name}</p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        <dt className="text-muted-foreground">{t('sap.material')}</dt>
        <dd className="tabular-nums">{shortMaterial(design.material)}</dd>
        <dt className="text-muted-foreground">{t('sap.project')}</dt>
        <dd className="tabular-nums">{design.wbs}</dd>
        <dt className="text-muted-foreground">{t('sap.revisions')}</dt>
        <dd className="tabular-nums">{design.revisions.join(', ') || '–'}</dd>
      </dl>
      {design.block_reason && <p className="mt-2 text-destructive">{t('sap.blocked', { reason: design.block_reason })}</p>}
      {design.successor && <p className="mt-1">{t('sap.successor', { successor: design.successor })}</p>}
      {notes.map((n) => (
        <p key={n.ref + n.message} className="mt-1 text-xs text-muted-foreground">
          {issueText(lang, n)} [{n.ref}]
        </p>
      ))}
    </section>
  )
}
