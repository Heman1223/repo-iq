/**
 * Chat state for one indexed repository.
 *
 * Keeps the transcript, sends questions with a trimmed history window, and
 * exposes an `isThinking` flag that drives the typing indicator. Switching
 * repository resets the conversation.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { askQuestion, getSummary, toApiError } from '@/lib/api'
import type { ApiError, ChatMessage, ChatTurn } from '@/types'

/** Turns replayed to the backend so follow-up questions resolve pronouns. */
const HISTORY_WINDOW = 6

function createId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

export interface UseChatResult {
  messages: ChatMessage[]
  isThinking: boolean
  error: ApiError | null
  sendMessage: (question: string) => Promise<void>
  requestSummary: () => Promise<void>
  clearChat: () => void
  dismissError: () => void
}

export function useChat(repoId: string | null): UseChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const isMountedRef = useRef(true)
  // Guards against double submits from Enter + click.
  const inFlightRef = useRef(false)

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  // A new repository means a new conversation.
  useEffect(() => {
    setMessages([])
    setError(null)
    setIsThinking(false)
    inFlightRef.current = false
  }, [repoId])

  const appendMessage = useCallback((message: ChatMessage) => {
    setMessages((current) => [...current, message])
  }, [])

  /** Shared wrapper: optimistic user turn, then resolve the assistant turn. */
  const runTurn = useCallback(
    async (
      question: string,
      resolve: (history: ChatTurn[]) => Promise<Omit<ChatMessage, 'id' | 'role' | 'createdAt'>>,
    ) => {
      if (!repoId || inFlightRef.current) return

      const trimmed = question.trim()
      if (!trimmed) return

      inFlightRef.current = true
      setError(null)
      setIsThinking(true)

      const history: ChatTurn[] = messages
        .filter((message) => !message.errorCode)
        .slice(-HISTORY_WINDOW)
        .map((message) => ({ role: message.role, content: message.content }))

      appendMessage({
        id: createId(),
        role: 'user',
        content: trimmed,
        createdAt: Date.now(),
      })

      try {
        const assistant = await resolve(history)
        if (!isMountedRef.current) return
        appendMessage({
          id: createId(),
          role: 'assistant',
          createdAt: Date.now(),
          animate: true,
          ...assistant,
        })
      } catch (caught) {
        if (!isMountedRef.current) return
        const apiError = toApiError(caught)
        setError(apiError)
        appendMessage({
          id: createId(),
          role: 'assistant',
          content: apiError.message,
          createdAt: Date.now(),
          errorCode: apiError.code,
        })
      } finally {
        inFlightRef.current = false
        if (isMountedRef.current) setIsThinking(false)
      }
    },
    [appendMessage, messages, repoId],
  )

  const sendMessage = useCallback(
    async (question: string) => {
      await runTurn(question, async (history) => {
        const response = await askQuestion(repoId!, question.trim(), history)
        return {
          content: response.answer,
          sources: response.sources,
          grounded: response.grounded,
          elapsedMs: response.elapsed_ms,
          retrievedChunks: response.retrieved_chunks,
        }
      })
    },
    [repoId, runTurn],
  )

  /** Uses `GET /summary`, which is cached server-side after the first call. */
  const requestSummary = useCallback(async () => {
    await runTurn('Summarize this repository', async () => {
      const response = await getSummary(repoId!)
      return {
        content: response.summary,
        sources: response.sources,
        grounded: true,
        retrievedChunks: response.sources.length,
      }
    })
  }, [repoId, runTurn])

  const clearChat = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  const dismissError = useCallback(() => setError(null), [])

  return { messages, isThinking, error, sendMessage, requestSummary, clearChat, dismissError }
}
