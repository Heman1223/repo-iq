/**
 * Chat area: empty state, transcript, typing indicator, suggestion chips and
 * the composer. Owns auto-scroll behaviour (and respects a user who has
 * scrolled up to read an earlier answer).
 */

import { AnimatePresence } from 'framer-motion'
import { Eraser, FileText, MessagesSquare, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

import { MessageBubble } from '@/components/chat/MessageBubble'
import { PromptBox } from '@/components/chat/PromptBox'
import { TypingIndicator } from '@/components/chat/TypingIndicator'
import { Button } from '@/components/ui/Button'
import { Chip } from '@/components/ui/Chip'
import { ErrorBanner } from '@/components/ui/ErrorBanner'
import { SUGGESTED_QUESTIONS } from '@/lib/constants'
import type { ApiError, ChatMessage } from '@/types'

export interface ChatPanelProps {
  messages: ChatMessage[]
  isThinking: boolean
  error: ApiError | null
  repoName: string
  repoUrl?: string
  defaultBranch?: string
  /** Disables input when the backend cannot answer (e.g. missing Gemini key). */
  canAsk: boolean
  disabledReason?: string
  /** Slot at the far left of the header (used for the sidebar toggle). */
  leadingAction?: ReactNode
  onSend: (question: string) => void
  onSummarize: () => void
  onClear: () => void
  onDismissError: () => void
}

export function ChatPanel({
  messages,
  isThinking,
  error,
  repoName,
  repoUrl,
  defaultBranch,
  canAsk,
  disabledReason,
  leadingAction,
  onSend,
  onSummarize,
  onClear,
  onDismissError,
}: ChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [isPinnedToBottom, setIsPinnedToBottom] = useState(true)

  // Track whether the user is at the bottom; only auto-scroll if they are.
  const handleScroll = useCallback(() => {
    const element = scrollRef.current
    if (!element) return
    const distanceFromBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight
    setIsPinnedToBottom(distanceFromBottom < 120)
  }, [])

  useEffect(() => {
    if (!isPinnedToBottom) return
    const element = scrollRef.current
    if (!element) return
    element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' })
  }, [messages, isThinking, isPinnedToBottom])

  const isEmpty = messages.length === 0

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* --------------------------------------------------------- panel header */}
      <header className="flex items-center gap-2 border-b border-line-soft px-4 py-3 sm:px-6">
        {leadingAction}
        <MessagesSquare className="size-4 shrink-0 text-faint" aria-hidden />
        <h2 className="min-w-0 flex-1 truncate text-[13px] font-medium text-muted">
          Chat · <span className="font-mono text-ink">{repoName}</span>
        </h2>

        <Button
          variant="ghost"
          size="sm"
          onClick={onSummarize}
          disabled={!canAsk || isThinking}
          leftIcon={<FileText className="size-3.5" />}
        >
          <span className="hidden sm:inline">Summary</span>
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClear}
          disabled={isEmpty || isThinking}
          leftIcon={<Eraser className="size-3.5" />}
        >
          <span className="hidden sm:inline">Clear</span>
        </Button>
      </header>

      {/* ------------------------------------------------------------ transcript */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6"
      >
        {isEmpty && !isThinking ? (
          <EmptyState repoName={repoName} />
        ) : (
          <div className="mx-auto max-w-4xl space-y-5">
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                repoUrl={repoUrl}
                defaultBranch={defaultBranch}
              />
            ))}
            <AnimatePresence>{isThinking && <TypingIndicator />}</AnimatePresence>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------- composer */}
      <div className="border-t border-line-soft bg-canvas/60 backdrop-blur-md">
        <ErrorBanner
          error={error}
          onDismiss={onDismissError}
          className="px-4 pt-3 sm:px-6"
        />

        <div className="flex flex-wrap gap-1.5 px-4 pt-3 sm:px-6">
          {SUGGESTED_QUESTIONS.slice(0, isEmpty ? 8 : 4).map((question) => (
            <Chip
              key={question}
              label={question}
              disabled={!canAsk || isThinking}
              onClick={() => onSend(question)}
            />
          ))}
        </div>

        <PromptBox
          onSubmit={onSend}
          disabled={!canAsk || isThinking}
          disabledReason={disabledReason}
        />
      </div>
    </div>
  )
}

function EmptyState({ repoName }: { repoName: string }) {
  return (
    <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center text-center">
      <span className="mb-4 inline-flex size-11 items-center justify-center rounded-xl border border-brand/25 bg-brand/10">
        <Sparkles className="size-5 text-brand-soft" aria-hidden />
      </span>
      <h3 className="text-lg font-semibold tracking-tight text-ink">
        Ask anything about this repository
      </h3>
      <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
        <span className="font-mono text-ink">{repoName}</span> is indexed and searchable. Every
        answer is grounded in the retrieved code and lists the files it came from.
      </p>
      <p className="mt-4 text-[12px] text-faint">
        Pick a suggestion below, or type your own question.
      </p>
    </div>
  )
}
