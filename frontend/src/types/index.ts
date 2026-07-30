/**
 * API contracts — a 1:1 mirror of `backend/app/models/schemas.py`.
 * Keeping them in one file makes drift between client and server obvious.
 */

export type IndexStage =
  | 'queued'
  | 'validating'
  | 'cloning'
  | 'reading_files'
  | 'chunking'
  | 'embedding'
  | 'storing'
  | 'finalizing'
  | 'ready'
  | 'failed'

export interface RepositoryMetadata {
  full_name: string
  name: string
  owner: string
  html_url: string
  description: string | null
  language: string | null
  stars: number
  forks: number
  watchers: number
  open_issues: number
  size_kb: number
  default_branch: string
  topics: string[]
  license_name: string | null
  is_fork: boolean
  created_at: string | null
  updated_at: string | null
  pushed_at: string | null
}

export interface IndexStats {
  total_files_scanned: number
  total_files_indexed: number
  total_files_skipped: number
  total_chunks: number
  total_characters: number
  embedding_model: string
  embedding_dimensions: number
  vector_count: number
  languages: Record<string, number>
  top_level_entries: string[]
  indexing_seconds: number
  indexed_at: string | null
}

export interface IndexStatus {
  repo_id: string
  full_name: string
  html_url: string
  stage: IndexStage
  progress: number
  message: string
  is_ready: boolean
  error_code: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  reused_existing_index: boolean
  metadata: RepositoryMetadata | null
  stats: IndexStats | null
}

export interface CloneResponse {
  repo_id: string
  full_name: string
  already_indexed: boolean
  status: IndexStatus
}

export interface SourceReference {
  file_path: string
  language: string | null
  chunk_index: number
  start_line: number | null
  end_line: number | null
  relevance: number
  snippet: string
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface AskResponse {
  repo_id: string
  question: string
  answer: string
  sources: SourceReference[]
  grounded: boolean
  model: string
  retrieved_chunks: number
  elapsed_ms: number
}

export interface SummaryResponse {
  repo_id: string
  full_name: string
  summary: string
  sources: SourceReference[]
  model: string
  cached: boolean
  generated_at: string
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  app: string
  version: string
  llm_configured: boolean
  llm_model: string
  embedding_model: string
  embedding_model_loaded: boolean
  vector_store_ready: boolean
  indexed_repositories: number
}

export interface IndexedRepositorySummary {
  repo_id: string
  full_name: string
  html_url: string
  stage: IndexStage
  indexed_at: string | null
  total_chunks: number
}

/** Normalised error shape produced by `lib/api.ts` for every failure. */
export interface ApiError {
  code: string
  message: string
  hint?: string | null
}

/* ----------------------------------------------------------- UI-only types */

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceReference[]
  grounded?: boolean
  elapsedMs?: number
  retrievedChunks?: number
  createdAt: number
  /** Set when the assistant turn failed, so the bubble can render as an error. */
  errorCode?: string
  /** Drives the typewriter reveal for freshly received answers only. */
  animate?: boolean
}
