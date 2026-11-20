import type { SapDesign } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { useI18n, type MessageKey } from '@/i18n'

// Status colors (decision 0014 addendum): in work = brand blue, released = done,
// blocked = error, obsolete = neutral. Sea is kept for "this value came from SAP".
const STATUS_STYLE: Record<string, string> = {
  IN_WORK: 'bg-hl-cobalt-soft text-hl-cobalt dark:bg-hl-cobalt/30 dark:text-hl-moon',
  RELEASED: 'bg-success/15 text-success',
  BLOCKED: 'bg-destructive/10 text-destructive',
  OBSOLETE: 'bg-muted text-muted-foreground line-through',
}

/** Material numbers are shown without leading zeros (03-title-block). */
const shortMaterial = (m: string) => m.replace(/^0+/, '') || m

export function SapCard({ design, notes }: { design: SapDesign; notes: { message: string; ref: string }[] }) {
  const { t } = useI18n()
  const known = ['IN_WORK', 'RELEASED', 'BLOCKED', 'OBSOLETE'].includes(design.status)
  return (
    <section aria-label={t('sap.card')} className="rounded-lg border bg-card p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="font-mono font-medium">{design.design_number}</p>
        <Badge className={STATUS_STYLE[design.status]} variant="secondary">
          {known ? t(`status.${design.status}` as MessageKey) : design.status}
        </Badge>
      </div>
      <p className="text-muted-foreground">{design.name}</p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        <dt className="text-muted-foreground">{t('sap.material')}</dt>
        <dd className="font-mono">{shortMaterial(design.material)}</dd>
        <dt className="text-muted-foreground">{t('sap.project')}</dt>
        <dd className="font-mono">{design.wbs}</dd>
        <dt className="text-muted-foreground">{t('sap.revisions')}</dt>
        <dd className="font-mono">{design.revisions.join(', ') || '–'}</dd>
      </dl>
      {design.block_reason && <p className="mt-2 text-destructive">{t('sap.blocked', { reason: design.block_reason })}</p>}
      {design.successor && <p className="mt-1">{t('sap.successor', { successor: design.successor })}</p>}
      {notes.map((n) => (
        <p key={n.ref + n.message} className="mt-1 text-xs text-muted-foreground">
          {n.message} [{n.ref}]
        </p>
      ))}
    </section>
  )
}
