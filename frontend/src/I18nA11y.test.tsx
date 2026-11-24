import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { translatePlural } from './i18n/context'
import { baseRoutes, jsonResponse, makeAction, renderWithProviders, sseResponse, stubFetch, user } from './test/helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

async function spanish() {
  await user.click(screen.getByRole('button', { name: 'ES' }))
}

const departments = (url: string) =>
  url === '/api/departments'
    ? jsonResponse([{ code: 'HW', name: 'Hardware Design', name_es: 'Diseño de Hardware' }])
    : undefined

function run(model_calls: number, status = 'answered') {
  return (url: string) =>
    url === '/api/runs/9'
      ? jsonResponse({ id: 9, provider: 'groq', model: 'gpt-oss', status, model_calls, trace: {} })
      : undefined
}

const answerOnly = (url: string) =>
  url === '/api/chat'
    ? sseResponse([
        ['conversation', { id: 'c1' }],
        ['run', { id: 9 }],
        ['message', { role: 'assistant', content: 'Hola' }],
        ['done', { conversation_id: 'c1', run_id: 9, status: 'answered' }],
      ])
    : undefined

describe('i18n and accessibility (decision 0017, block C)', () => {
  it('keeps <html lang> in step with the language', async () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)
    expect(document.documentElement.lang).toBe('en')

    await user.click(screen.getByRole('button', { name: 'ES' }))

    expect(document.documentElement.lang).toBe('es')
  })

  it('shows department names and card labels in Spanish', async () => {
    stubFetch(
      departments,
      (url) =>
        url === '/api/chat'
          ? sseResponse([
              ['conversation', { id: 'c1' }],
              ['pending_action', { action: makeAction() }],
              ['done', { status: 'answered' }],
            ])
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await spanish()

    expect(await screen.findByRole('option', { name: 'HW – Diseño de Hardware' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Guíame paso a paso' }))
    const card = await screen.findByRole('region', { name: '¿Crear este diseño?' })
    expect(within(card).getByText('Número de diseño')).toBeInTheDocument()
    expect(within(card).getByText('Diseñador')).toBeInTheDocument()
    expect(within(card).getByText('HW – Diseño de Hardware')).toBeInTheDocument()
  })

  it('uses singular and plural forms', () => {
    expect(translatePlural('es', 'steps.calls', 1)).toBe('1 llamada al modelo')
    expect(translatePlural('es', 'steps.calls', 3)).toBe('3 llamadas al modelo')
    expect(translatePlural('en', 'steps.calls', 1)).toBe('1 model call')
    expect(translatePlural('en', 'steps.calls', 0)).toBe('0 model calls')
  })

  it('the steps drawer says when an answer used no tools, with a translated status', async () => {
    stubFetch(answerOnly, run(1), ...baseRoutes)
    renderWithProviders(<App />)
    await spanish()
    await user.click(screen.getByRole('button', { name: 'Guíame paso a paso' }))
    await screen.findByText('Hola')

    await user.click(screen.getByRole('button', { name: 'Pasos del agente' }))

    expect(await screen.findByText('Esta respuesta no usó herramientas: el modelo respondió directamente.')).toBeInTheDocument()
    expect(await screen.findByText('Ejecución 9: groq / gpt-oss, 1 llamada al modelo, respondida')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeInTheDocument()
  })
})
