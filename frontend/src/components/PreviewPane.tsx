import { useState } from 'react'

import { previewUrl } from '@/api/client'
import type { PreviewTarget } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useI18n } from '@/i18n'

export function PreviewPane({ target }: { target: PreviewTarget | null }) {
  const { t } = useI18n()
  const [failedKey, setFailedKey] = useState('')
  const key = target ? `${target.department}/${target.design_number}/${target.revision}` : ''

  const failed = failedKey === key

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="font-heading text-lg">{t('preview.title')}</CardTitle>
        {target && (
          <Button size="sm" variant="outline" asChild>
            <a href={previewUrl(target, 'pdf')} target="_blank" rel="noreferrer">
              {t('preview.open_pdf')}
            </a>
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {!target && <p className="text-sm text-muted-foreground">{t('preview.empty')}</p>}
        {target && failed && <p className="text-sm text-muted-foreground">{t('preview.missing')}</p>}
        {target && !failed && (
          <img
            src={previewUrl(target, 'svg')}
            alt={t('preview.alt', { number: target.design_number, rev: target.revision })}
            className="max-h-96 w-full rounded border bg-white object-contain"
            onError={() => setFailedKey(key)}
          />
        )}
      </CardContent>
    </Card>
  )
}
