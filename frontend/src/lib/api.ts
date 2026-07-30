/**
 * Typed API client.
 *
 * Every network call in the app goes through this module: one axios instance,
 * one error shape (`ApiError`), no fetch calls scattered through components.
 */

import axios, { AxiosError, type AxiosInstance } from 'axios'
import type {
  ApiError,
  AskResponse,
  ChatTurn,
  CloneResponse,
  HealthResponse,
  IndexStatus,
  IndexedRepositorySummary,
  SummaryResponse,
} from '@/types'

/** Base URL is environment-driven so deployments need no code changes. */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const client: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 180_000),
  headers: { 'Content-Type': 'application/json' },
})

/** Backend error envelope: `{ error: { code, message, hint } }`. */
interface ErrorEnvelope {
  error?: { code?: string; message?: string; hint?: string | null }
  detail?: string
}

/**
 * Collapse anything axios can throw into a predictable `ApiError`.
 * Components can then branch on `code` instead of parsing messages.
 */
export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ErrorEnvelope>
    const envelope = axiosError.response?.data

    if (envelope?.error?.message) {
      return {
        code: envelope.error.code ?? 'api_error',
        message: envelope.error.message,
        hint: envelope.error.hint ?? null,
      }
    }
    if (typeof envelope?.detail === 'string') {
      return { code: 'api_error', message: envelope.detail }
    }
    if (axiosError.code === 'ECONNABORTED') {
      return {
        code: 'timeout',
        message: 'The request took too long. Large repositories can take a while — try again.',
      }
    }
    if (!axiosError.response) {
      return {
        code: 'network_error',
        message: `Cannot reach the backend at ${API_BASE_URL}. Is the FastAPI server running?`,
      }
    }
    return {
      code: 'api_error',
      message: `Request failed with status ${axiosError.response.status}.`,
    }
  }

  return {
    code: 'unknown_error',
    message: error instanceof Error ? error.message : 'An unexpected error occurred.',
  }
}

/* ------------------------------------------------------------------ routes */

/** `POST /clone` — start (or reuse) an index for a repository URL. */
export async function cloneRepository(
  repoUrl: string,
  forceReindex = false,
): Promise<CloneResponse> {
  const { data } = await client.post<CloneResponse>('/clone', {
    repo_url: repoUrl,
    force_reindex: forceReindex,
  })
  return data
}

/** `GET /status` — poll pipeline progress. */
export async function getIndexStatus(repoId: string): Promise<IndexStatus> {
  const { data } = await client.get<IndexStatus>('/status', { params: { repo_id: repoId } })
  return data
}

/** `POST /ask` — grounded question answering over the indexed repository. */
export async function askQuestion(
  repoId: string,
  question: string,
  history: ChatTurn[] = [],
): Promise<AskResponse> {
  const { data } = await client.post<AskResponse>('/ask', {
    repo_id: repoId,
    question,
    history,
  })
  return data
}

/** `GET /summary` — AI onboarding briefing (cached server-side). */
export async function getSummary(repoId: string, refresh = false): Promise<SummaryResponse> {
  const { data } = await client.get<SummaryResponse>('/summary', {
    params: { repo_id: repoId, refresh },
  })
  return data
}

/** `GET /health` — used by the status pill in the top bar. */
export async function getHealth(): Promise<HealthResponse> {
  const { data } = await client.get<HealthResponse>('/health')
  return data
}

/** `GET /repositories` — everything indexed on this server. */
export async function listRepositories(): Promise<IndexedRepositorySummary[]> {
  const { data } = await client.get<{ repositories: IndexedRepositorySummary[] }>('/repositories')
  return data.repositories
}

/** `DELETE /repositories/{id}` — drop vectors and cached metadata. */
export async function deleteRepository(repoId: string): Promise<void> {
  await client.delete(`/repositories/${encodeURIComponent(repoId)}`)
}
