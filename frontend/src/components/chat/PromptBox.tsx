/**
 * Bottom composer.
 *
 * Auto-growing textarea, Enter to send / Shift+Enter for a newline, character
 * counter and a disabled state that explains itself.
 */

import { ArrowUp, CornerDownLeft } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

import { MAX_QUESTION_LENGTH } from '@/lib/constants'
import { cx } from '@/lib/format'

const MAX_TEXTAREA_HEIGHT = 180

export interface PromptBoxProps {
  onSubmit: (question: string) => void
  disabled?: boolean
  /** Shown as the reason the composer is unavailable. */
  disabledReason?: string
  placeholder?: string
}

export function PromptBox({
  onSubmit,
  disabled = false,
  disabledReason,
  placeholder = 'Ask anything about this repository…',
}: PromptBoxProps) {
  const [value, setValue] = useState('')
  const [isFocused, setIsFocused] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Grow with content, up to a cap, then scroll.
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`
  }, [value])

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  const isNearLimit = value.length > MAX_QUESTION_LENGTH * 0.8
  const canSubmit = value.trim().length > 0 && !disabled

  return (
    <div className="px-4 pb-4 pt-2 sm:px-6 sm:pb-5">
      <div
        className={cx(
          'rounded-2xl border bg-surface/70 p-2 backdrop-blur-md transition-all duration-200',
          isFocused
            ? 'border-brand/50 shadow-[0_0_0_1px_rgba(59,130,246,0.35),0_16px_40px_-28px_rgba(59,130,246,0.7)]'
            : 'border-line shadow-[0_8px_28px_-24px_rgba(1,4,9,0.9)]',
          disabled && 'opacity-70',
        )}
      >
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            maxLength={MAX_QUESTION_LENGTH}
            disabled={disabled}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={disabled ? (disabledReason ?? placeholder) : placeholder}
            aria-label="Question"
            className={cx(
              'max-h-[180px] min-h-10 flex-1 resize-none bg-transparent px-2.5 py-2',
              'text-[14.5px] leading-relaxed text-ink outline-none',
              'placeholder:text-faint disabled:cursor-not-allowed',
            )}
          />

          <button
            type="button"
            onClick={submit}
            disabled={!canSubmit}
            aria-label="Send question"
            className={cx(
              'mb-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-xl transition-all duration-200',
              canSubmit
                ? 'bg-brand text-white hover:bg-brand-strong hover:shadow-[0_0_0_1px_rgba(96,165,250,0.45)]'
                : 'cursor-not-allowed bg-surface-raised text-faint',
            )}
          >
            <ArrowUp className="size-4" aria-hidden />
          </button>
        </div>

        <div className="flex items-center justify-between px-2.5 pb-0.5 pt-1">
          <p className="flex items-center gap-1.5 text-[11px] text-faint">
            <CornerDownLeft className="size-3" aria-hidden />
            Enter to send · Shift+Enter for a new line
          </p>
          {isNearLimit && (
            <p className={cx('font-mono text-[11px]', value.length >= MAX_QUESTION_LENGTH ? 'text-danger' : 'text-faint')}>
              {value.length}/{MAX_QUESTION_LENGTH}
            </p>
          )}
        </div>
      </div>

      <p className="mt-2 text-center text-[11px] text-faint">
        Answers are generated only from the indexed repository and cite their sources.
      </p>
    </div>
  )
}
