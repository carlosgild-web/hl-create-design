import { Button } from '@/components/ui/button'
import { DemoGuide } from '@/demo-guide/DemoGuide'
import { useI18n } from '@/i18n'

export function Header() {
  const { t, lang, setLang } = useI18n()

  return (
    <header>
      <DemoGuide />
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4">
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="size-9 rounded" />
          <div>
            <p className="text-xs text-muted-foreground">{t('app.company')}</p>
            <h1 className="font-heading text-xl font-semibold">{t('app.title')}</h1>
          </div>
        </div>
        <div role="group" aria-label={t('lang.label')} className="flex gap-1">
          {(['en', 'es'] as const).map((code) => (
            <Button
              key={code}
              size="sm"
              variant={lang === code ? 'default' : 'outline'}
              aria-pressed={lang === code}
              onClick={() => setLang(code)}
            >
              {code.toUpperCase()}
            </Button>
          ))}
        </div>
      </div>
    </header>
  )
}
