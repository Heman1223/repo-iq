/** Glass surfaces: the single card primitive used across the app. */

import { motion } from 'framer-motion'
import type { HTMLAttributes, ReactNode } from 'react'

import { cx } from '@/lib/format'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** `glass` for panels, `subtle` for nested/secondary surfaces. */
  tone?: 'glass' | 'subtle'
  /** Adds a blue hover ring — only for cards that are interactive. */
  interactive?: boolean
  padded?: boolean
}

export function Card({
  tone = 'glass',
  interactive = false,
  padded = true,
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={cx(
        'rounded-2xl',
        tone === 'glass' ? 'glass' : 'glass-subtle',
        padded && 'p-5',
        interactive &&
          'transition-all duration-300 hover:border-brand/35 hover:shadow-[0_0_0_1px_rgba(59,130,246,0.18),0_16px_40px_-24px_rgba(59,130,246,0.5)]',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}

export interface SectionProps {
  title: string
  icon?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}

/** Labelled block used throughout the sidebar. */
export function Section({ title, icon, action, children, className }: SectionProps) {
  return (
    <section className={cx('space-y-3', className)}>
      <header className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
          {icon}
          {title}
        </h3>
        {action}
      </header>
      {children}
    </section>
  )
}

/** Fade-and-rise entrance used for page-level regions. */
export function FadeIn({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode
  delay?: number
  className?: string
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}
