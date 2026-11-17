import { I18nProvider } from '@/i18n'
import CreateDesignPage from '@/pages/CreateDesignPage'

export default function App() {
  return (
    <I18nProvider>
      <CreateDesignPage />
    </I18nProvider>
  )
}
