/** "Searching the repository…" placeholder shown while an answer is pending. */

import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'

import { AnswerSkeleton } from '@/components/ui/Skeleton'

export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="flex gap-2.5"
    >
      <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-lg border border-brand/30 bg-brand/12">
        <Sparkles className="size-3.5 animate-pulse text-brand-soft" aria-hidden />
      </span>

      <div className="glass-subtle min-w-0 flex-1 rounded-2xl rounded-tl-md px-4 py-3.5 sm:max-w-md">
        <div className="mb-3 flex items-center gap-2">
          <Dots />
          <span className="text-[12.5px] text-muted">Retrieving relevant code…</span>
        </div>
        <AnswerSkeleton />
      </div>
    </motion.div>
  )
}

function Dots() {
  return (
    <span className="flex items-center gap-1" aria-hidden>
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          className="size-1.5 rounded-full bg-brand"
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
          transition={{ duration: 1.1, repeat: Infinity, delay: index * 0.16 }}
        />
      ))}
    </span>
  )
}
