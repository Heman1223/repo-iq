/** Chips and badges: clickable suggestions, status pills and metadata tags. */

import { motion } from 'framer-motion'
import type { HTMLAttributes, ReactNode } from 'react'

import { cx } from '@/lib/format'

export interface ChipProps {
  label: string
  icon?: ReactNode
  onClick?: () => void
  disabled?: boolean
  className?: string
}

/** Clickable suggested-question chip. */
export function Chip({ label, icon, onClick, disabled, className }: ChipProps) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={disabled}
      whileHover={disabled ? undefined : { y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 480, damping: 30 }}
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border border-line-soft bg-surface/60',
        'px-3 py-1.5 text-[13px] text-muted backdrop-blur-sm transition-colors duration-200',
        'hover:border-brand/40 hover:bg-brand/10 hover:text-ink',
        'disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:border-line-soft',
        'disabled:hover:bg-surface/60 disabled:hover:text-muted',
        className,
      )}
    >
      {icon}
      {label}
    </motion.button>
  )
}

type BadgeTone = 'neutral' | 'brand' | 'success' | 'danger' | 'warning'

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: 'border-line bg-surface-raised/70 text-muted',
  brand: 'border-brand/35 bg-brand/12 text-brand-soft',
  success: 'border-success/35 bg-success/12 text-success',
  danger: 'border-danger/35 bg-danger/12 text-danger',
  warning: 'border-warning/35 bg-warning/12 text-warning',
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode
  tone?: BadgeTone
}

export function Badge({ children, tone = 'neutral', className, ...rest }: BadgeProps) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5',
        'text-[11px] font-medium tracking-wide',
        BADGE_TONES[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  )
}

/** Small pulsing dot used inside status badges. */
export function StatusDot({ tone = 'brand' }: { tone?: BadgeTone }) {
  const colors: Record<BadgeTone, string> = {
    neutral: 'bg-faint',
    brand: 'bg-brand',
    success: 'bg-success',
    danger: 'bg-danger',
    warning: 'bg-warning',
  }
  return (
    <span className="relative flex size-1.5">
      <span
        className={cx('absolute inline-flex size-full animate-ping rounded-full opacity-60', colors[tone])}
      />
      <span className={cx('relative inline-flex size-1.5 rounded-full', colors[tone])} />
    </span>
  )
}
