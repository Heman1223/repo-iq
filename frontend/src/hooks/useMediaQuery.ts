/**
 * Subscribes to a CSS media query.
 *
 * Used so layout variants can be chosen in JS and rendered *once*, instead of
 * mounting both a desktop and a mobile copy and hiding one with CSS.
 */

import { useEffect, useState } from 'react'

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  )

  useEffect(() => {
    const mediaQuery = window.matchMedia(query)
    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches)

    setMatches(mediaQuery.matches)
    mediaQuery.addEventListener('change', onChange)
    return () => mediaQuery.removeEventListener('change', onChange)
  }, [query])

  return matches
}

/** Matches the Tailwind `lg` breakpoint used for the two-column layout. */
export const DESKTOP_QUERY = '(min-width: 1024px)'
