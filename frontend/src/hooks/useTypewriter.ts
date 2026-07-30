/**
 * Reveals text progressively, like a terminal typing out a response.
 *
 * Reveals in chunks on a timer rather than character-by-character so long
 * answers stay smooth (and cheap) to render. Honours `prefers-reduced-motion`
 * by skipping the animation entirely.
 */

import { useEffect, useRef, useState } from 'react'

const TICK_MS = 16
const CHARS_PER_TICK = 9

export interface UseTypewriterResult {
  text: string
  isTyping: boolean
  /** Reveal everything immediately (used by the "skip" affordance). */
  skip: () => void
}

export function useTypewriter(fullText: string, enabled: boolean): UseTypewriterResult {
  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  const shouldAnimate = enabled && !prefersReducedMotion
  const [revealed, setRevealed] = useState(() => (shouldAnimate ? 0 : fullText.length))
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    if (!shouldAnimate) {
      setRevealed(fullText.length)
      return
    }

    setRevealed(0)
    let position = 0

    const tick = () => {
      position = Math.min(position + CHARS_PER_TICK, fullText.length)
      setRevealed(position)
      if (position < fullText.length) {
        timerRef.current = window.setTimeout(tick, TICK_MS)
      }
    }
    timerRef.current = window.setTimeout(tick, TICK_MS)

    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    }
  }, [fullText, shouldAnimate])

  return {
    text: fullText.slice(0, revealed),
    isTyping: revealed < fullText.length,
    skip: () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current)
      setRevealed(fullText.length)
    },
  }
}
