/**
 * Two-column workspace: repository dashboard on the left, chat on the right.
 *
 * Desktop-first. Below `lg` the dashboard becomes an overlay drawer and starts
 * closed. The dashboard is rendered exactly once — the layout variant is chosen
 * in JS rather than mounting both and hiding one with CSS.
 */

import { AnimatePresence, motion } from 'framer-motion'
import { PanelLeftClose, PanelLeftOpen, X } from 'lucide-react'
import { useState } from 'react'

import { ChatPanel } from '@/components/chat/ChatPanel'
import { IndexingInlineNotice } from '@/components/indexing/IndexingScreen'
import { RepositorySidebar } from '@/components/workspace/RepositorySidebar'
import { IconButton } from '@/components/ui/Button'
import { useChat } from '@/hooks/useChat'
import { DESKTOP_QUERY, useMediaQuery } from '@/hooks/useMediaQuery'
import type { IndexStatus } from '@/types'

export interface WorkspaceProps {
  status: IndexStatus
  /** Set while a background re-index is running for this repository. */
  reindexStatus?: IndexStatus | null
  canAsk: boolean
  askDisabledReason?: string
  onDeleteIndex: () => void
}

export function Workspace({
  status,
  reindexStatus,
  canAsk,
  askDisabledReason,
  onDeleteIndex,
}: WorkspaceProps) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const chat = useChat(status.repo_id)

  // One state per layout, each with its own default (column open, drawer closed).
  // Deriving the visible flag from the breakpoint — rather than syncing a single
  // flag in an effect — means a resize can never mount both variants for a frame.
  const [isColumnOpen, setIsColumnOpen] = useState(true)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)

  const isInfoOpen = isDesktop ? isColumnOpen : isDrawerOpen
  const toggleInfo = () =>
    isDesktop ? setIsColumnOpen((open) => !open) : setIsDrawerOpen((open) => !open)

  const dashboard = (
    <div className="flex h-full flex-col gap-3">
      {reindexStatus && <IndexingInlineNotice status={reindexStatus} />}
      <div className="min-h-0 flex-1">
        <RepositorySidebar status={status} onDelete={onDeleteIndex} />
      </div>
    </div>
  )

  return (
    <main className="mx-auto flex h-[calc(100vh-3.5rem)] w-full max-w-[1600px] gap-4 px-4 py-4 sm:px-6">
      {/* -------------------------------------------------- desktop info column */}
      <AnimatePresence initial={false}>
        {isDesktop && isInfoOpen && (
          <motion.aside
            key="sidebar"
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: 320 }}
            exit={{ opacity: 0, width: 0 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="shrink-0 overflow-hidden"
          >
            <div className="h-full w-[320px]">{dashboard}</div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* --------------------------------------------------- mobile info drawer */}
      <AnimatePresence>
        {!isDesktop && isInfoOpen && (
          <motion.div
            key="drawer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 flex"
          >
            <button
              type="button"
              aria-label="Close repository panel"
              onClick={() => setIsDrawerOpen(false)}
              className="absolute inset-0 bg-canvas-inset/70 backdrop-blur-sm"
            />
            <motion.div
              initial={{ x: -24 }}
              animate={{ x: 0 }}
              exit={{ x: -24 }}
              transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
              className="relative m-3 flex w-[min(21rem,88vw)] flex-col"
            >
              <div className="mb-2 flex justify-end">
                <IconButton label="Close repository panel" onClick={() => setIsDrawerOpen(false)}>
                  <X className="size-4" />
                </IconButton>
              </div>
              <div className="min-h-0 flex-1">{dashboard}</div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ----------------------------------------------------------------- chat */}
      <section className="glass min-w-0 flex-1 overflow-hidden rounded-2xl">
        <ChatPanel
          messages={chat.messages}
          isThinking={chat.isThinking}
          error={chat.error}
          repoName={status.full_name}
          repoUrl={status.html_url}
          defaultBranch={status.metadata?.default_branch}
          canAsk={canAsk}
          disabledReason={askDisabledReason}
          onSend={chat.sendMessage}
          onSummarize={chat.requestSummary}
          onClear={chat.clearChat}
          onDismissError={chat.dismissError}
          leadingAction={
            <IconButton
              label={isInfoOpen ? 'Hide repository panel' : 'Show repository panel'}
              onClick={toggleInfo}
              className="size-8"
            >
              {isInfoOpen ? (
                <PanelLeftClose className="size-4" />
              ) : (
                <PanelLeftOpen className="size-4" />
              )}
            </IconButton>
          }
        />
      </section>
    </main>
  )
}
