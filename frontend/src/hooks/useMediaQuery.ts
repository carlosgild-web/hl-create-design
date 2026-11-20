import { useSyncExternalStore } from 'react'

/** True while the media query matches. Without `matchMedia` (tests) it is `fallback`. */
export function useMediaQuery(query: string, fallback = true): boolean {
  return useSyncExternalStore(
    (notify) => {
      if (typeof window === 'undefined' || !window.matchMedia) return () => {}
      const list = window.matchMedia(query)
      list.addEventListener('change', notify)
      return () => list.removeEventListener('change', notify)
    },
    () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(query).matches : fallback),
  )
}

/** Tailwind's `lg` breakpoint: two columns from here, tabs below. */
export const DESKTOP = '(min-width: 1024px)'
