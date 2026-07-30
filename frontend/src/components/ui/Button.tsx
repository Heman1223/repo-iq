/** Buttons: rounded, glassy, blue-accented, with a restrained hover glow. */

import { motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cx } from '@/lib/format'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

/**
 * React's drag/animation handlers collide with framer-motion's own props of the
 * same name, so they are dropped from the public surface of this component.
 */
type MotionSafeButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  'onDrag' | 'onDragStart' | 'onDragEnd' | 'onAnimationStart' | 'onAnimationEnd'
>

export interface ButtonProps extends MotionSafeButtonProps {
  variant?: Variant
  size?: Size
  isLoading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

const BASE =
  'relative inline-flex items-center justify-center gap-2 rounded-xl font-medium ' +
  'transition-all duration-200 select-none disabled:cursor-not-allowed disabled:opacity-50'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-brand text-white shadow-[0_1px_0_0_rgba(255,255,255,0.12)_inset,0_6px_18px_-10px_rgba(59,130,246,0.9)] ' +
    'hover:bg-brand-strong hover:shadow-[0_0_0_1px_rgba(96,165,250,0.4),0_8px_26px_-8px_rgba(59,130,246,0.65)]',
  secondary:
    'glass-subtle text-ink hover:border-line hover:bg-surface-raised/70 ' +
    'hover:shadow-[0_0_0_1px_rgba(59,130,246,0.22)]',
  ghost: 'text-muted hover:bg-surface-raised/60 hover:text-ink',
  danger:
    'border border-danger/40 bg-danger/10 text-danger hover:border-danger/60 hover:bg-danger/16',
}

const SIZES: Record<Size, string> = {
  sm: 'h-8 px-3 text-[13px]',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-[15px]',
}

export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <motion.button
      whileHover={disabled || isLoading ? undefined : { y: -1 }}
      whileTap={disabled || isLoading ? undefined : { scale: 0.985 }}
      transition={{ type: 'spring', stiffness: 480, damping: 30 }}
      className={cx(BASE, VARIANTS[variant], SIZES[size], className)}
      disabled={disabled || isLoading}
      {...rest}
    >
      {isLoading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : leftIcon}
      {children}
      {!isLoading && rightIcon}
    </motion.button>
  )
}

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
  children: ReactNode
}

/** Square, icon-only button. `label` is required for accessibility. */
export function IconButton({ label, children, className, ...rest }: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cx(
        'inline-flex size-9 items-center justify-center rounded-lg border border-transparent',
        'text-muted transition-colors duration-200',
        'hover:border-line hover:bg-surface-raised/70 hover:text-ink',
        'disabled:cursor-not-allowed disabled:opacity-40',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
