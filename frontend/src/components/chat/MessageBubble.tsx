/**
 * One chat turn.
 *
 * User turns are compact blue bubbles; assistant turns are dark glass cards with
 * markdown, citations and a small metadata footer (latency, chunks retrieved).
 */

import { motion } from 'framer-motion'
import { AlertTriangle, Check, Copy, Search, Sparkles, User } from 'lucide-react'
import { useState } from 'react'

import { Markdown } from '@/components/chat/Markdown'
import { SourceCitations } from '@/components/chat/SourceCitations'
import { IconButton } from '@/components/ui/Button'
import { useTypewriter } from '@/hooks/useTypewriter'
import { cx, formatMilliseconds } from '@/lib/format'
import type { ChatMessage } from '@/types'

export interface MessageBubbleProps {
  message: ChatMessage
  repoUrl?: string
  defaultBranch?: string
}

export function MessageBubble({ message, repoUrl, defaultBranch }: MessageBubbleProps) {
  return message.role === 'user' ? (
    <UserBubble message={message} />
  ) : (
    <AssistantBubble message={message} repoUrl={repoUrl} defaultBranch={defaultBranch} />
  )
}

function UserBubble({ message }: { message: ChatMessage }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className="flex justify-end gap-2.5"
    >
      <div className="max-w-[min(42rem,88%)] rounded-2xl rounded-br-md border border-brand/40 bg-brand/16 px-3.5 py-2.5">
        <p className="whitespace-pre-wrap text-[14.5px] leading-relaxed text-ink">
          {message.content}
        </p>
      </div>
      <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-lg border border-line bg-surface">
        <User className="size-3.5 text-muted" aria-hidden />
      </span>
    </motion.div>
  )
}

function AssistantBubble({
  message,
  repoUrl,
  defaultBranch,
}: {
  message: ChatMessage
  repoUrl?: string
  defaultBranch?: string
}) {
  const [copied, setCopied] = useState(false)
  const isError = Boolean(message.errorCode)
  const { text, isTyping, skip } = useTypewriter(message.content, Boolean(message.animate) && !isError)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      // Clipboard permission denied — nothing useful to show the user.
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className="flex gap-2.5"
    >
      <span
        className={cx(
          'mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-lg border',
          isError ? 'border-danger/40 bg-danger/10' : 'border-brand/30 bg-brand/12',
        )}
      >
        {isError ? (
          <AlertTriangle className="size-3.5 text-danger" aria-hidden />
        ) : (
          <Sparkles className="size-3.5 text-brand-soft" aria-hidden />
        )}
      </span>

      <div
        className={cx(
          'group min-w-0 max-w-[min(52rem,92%)] rounded-2xl rounded-tl-md border px-4 py-3',
          isError ? 'border-danger/35 bg-danger/6' : 'glass-subtle',
        )}
      >
        {isError ? (
          <p className="text-[14px] leading-relaxed text-ink">{message.content}</p>
        ) : (
          <>
            <div onClick={isTyping ? skip : undefined} role={isTyping ? 'button' : undefined}>
              <Markdown content={text} />
              {isTyping && (
                <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-brand align-middle" />
              )}
            </div>

            {message.grounded === false && (
              <p className="mt-2.5 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/8 px-2.5 py-2 text-[12.5px] text-muted">
                <Search className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden />
                Nothing in the indexed repository matched this question. Try naming a specific
                file, function or feature.
              </p>
            )}

            {!isTyping && message.sources && message.sources.length > 0 && (
              <SourceCitations
                sources={message.sources}
                repoUrl={repoUrl}
                defaultBranch={defaultBranch}
              />
            )}

            {/* Footer: transparency about how the answer was produced. */}
            {!isTyping && (
              <div className="mt-2.5 flex items-center gap-3 text-[11px] text-faint">
                {message.retrievedChunks !== undefined && message.retrievedChunks > 0 && (
                  <span>{message.retrievedChunks} chunks retrieved</span>
                )}
                {message.elapsedMs !== undefined && message.elapsedMs > 0 && (
                  <span>{formatMilliseconds(message.elapsedMs)}</span>
                )}
                <IconButton
                  label={copied ? 'Copied' : 'Copy answer'}
                  onClick={copy}
                  className="ml-auto size-7 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                >
                  {copied ? (
                    <Check className="size-3.5 text-success" />
                  ) : (
                    <Copy className="size-3.5" />
                  )}
                </IconButton>
              </div>
            )}
          </>
        )}
      </div>
    </motion.div>
  )
}
