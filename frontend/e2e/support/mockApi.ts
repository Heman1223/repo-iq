/**
 * Deterministic backend doubles for the browser tests.
 *
 * The UI is verified against fixed payloads rather than a live index, so the
 * specs are fast, offline and independent of any API key. The payload shapes are
 * copied from real responses captured from the running backend.
 */

import type { Page, Route } from '@playwright/test'
import type {
  AskResponse,
  CloneResponse,
  HealthResponse,
  IndexStatus,
  RepositoryMetadata,
  IndexStats,
  SummaryResponse,
} from '../../src/types'

export const HEALTHY: HealthResponse = {
  status: 'ok',
  app: 'GitHub Repository AI Assistant',
  version: '1.0.0',
  llm_configured: true,
  llm_model: 'gemini-2.5-flash',
  embedding_model: 'sentence-transformers/all-MiniLM-L6-v2',
  embedding_model_loaded: true,
  vector_store_ready: true,
  indexed_repositories: 1,
}

export const DEGRADED: HealthResponse = { ...HEALTHY, status: 'degraded', llm_configured: false }

const METADATA: RepositoryMetadata = {
  full_name: 'pallets/flask',
  name: 'flask',
  owner: 'pallets',
  html_url: 'https://github.com/pallets/flask',
  description: 'The Python micro framework for building web applications.',
  language: 'Python',
  stars: 68421,
  forks: 16250,
  watchers: 2100,
  open_issues: 12,
  size_kb: 10240,
  default_branch: 'main',
  topics: ['python', 'flask', 'wsgi', 'web-framework'],
  license_name: 'BSD-3-Clause',
  is_fork: false,
  created_at: '2010-04-06T11:11:59Z',
  updated_at: '2026-07-20T08:00:00Z',
  pushed_at: '2026-07-28T14:30:00Z',
}

const STATS: IndexStats = {
  total_files_scanned: 225,
  total_files_indexed: 208,
  total_files_skipped: 17,
  total_chunks: 1328,
  total_characters: 1_284_991,
  embedding_model: 'sentence-transformers/all-MiniLM-L6-v2',
  embedding_dimensions: 384,
  vector_count: 1328,
  languages: { python: 80, rst: 79, html: 20, text: 13, toml: 5, markdown: 3 },
  top_level_entries: ['docs/', 'examples/', 'src/', 'tests/', 'CHANGES.rst', 'pyproject.toml', 'README.md'],
  indexing_seconds: 119.09,
  indexed_at: '2026-07-30T12:31:53Z',
}

export const READY_STATUS: IndexStatus = {
  repo_id: 'pallets__flask',
  full_name: 'pallets/flask',
  html_url: 'https://github.com/pallets/flask',
  stage: 'ready',
  progress: 1,
  message: 'Indexed 208 files into 1328 chunks',
  is_ready: true,
  error_code: null,
  error_message: null,
  started_at: '2026-07-30T12:29:54Z',
  completed_at: '2026-07-30T12:31:53Z',
  reused_existing_index: false,
  metadata: METADATA,
  stats: STATS,
}

/** Stage sequence the loading screen is expected to walk through. */
export const PROGRESS_SEQUENCE: IndexStatus[] = [
  { ...READY_STATUS, stage: 'cloning', progress: 0.2, message: 'Cloning repository', is_ready: false, stats: null, metadata: METADATA },
  { ...READY_STATUS, stage: 'reading_files', progress: 0.35, message: 'Read 208 files', is_ready: false, stats: null },
  { ...READY_STATUS, stage: 'embedding', progress: 0.64, message: 'Generating embeddings (620/1328 chunks)', is_ready: false },
  { ...READY_STATUS, stage: 'storing', progress: 0.9, message: 'Creating vector database', is_ready: false },
  READY_STATUS,
]

export const GROUNDED_ANSWER: AskResponse = {
  repo_id: 'pallets__flask',
  question: 'How is the request context created?',
  answer: [
    'The request context is created in `src/flask/ctx.py` by the `RequestContext` class.',
    '',
    '### How it works',
    '',
    '- `Flask.request_context()` builds a `RequestContext` for the incoming WSGI environ.',
    '- Pushing it makes `request` and `session` available.',
    '',
    '```python',
    'class RequestContext:',
    '    def push(self) -> None:',
    '        self._cv_tokens.append(_cv_request.set(self))',
    '```',
  ].join('\n'),
  sources: [
    {
      file_path: 'src/flask/ctx.py',
      language: 'python',
      chunk_index: 4,
      start_line: 118,
      end_line: 151,
      relevance: 0.798,
      snippet: 'class RequestContext:\n    """The request context contains per-request information."""',
    },
    {
      file_path: 'docs/reqcontext.rst',
      language: 'rst',
      chunk_index: 0,
      start_line: 1,
      end_line: 26,
      relevance: 0.746,
      snippet: 'The Request Context\n===================',
    },
  ],
  grounded: true,
  model: 'gemini-2.5-flash',
  retrieved_chunks: 8,
  elapsed_ms: 2310,
}

export const SENTINEL_ANSWER: AskResponse = {
  ...GROUNDED_ANSWER,
  question: 'Where is the Kafka consumer configured?',
  answer: "I couldn't find that information in the indexed repository.",
  sources: [],
  grounded: false,
  retrieved_chunks: 0,
}

export const SUMMARY: SummaryResponse = {
  repo_id: 'pallets__flask',
  full_name: 'pallets/flask',
  summary: '## Overview\n\nFlask is a lightweight WSGI web application framework.\n\n## Tech Stack\n\n- Werkzeug\n- Jinja2',
  sources: GROUNDED_ANSWER.sources,
  model: 'gemini-2.5-flash',
  cached: false,
  generated_at: '2026-07-30T13:00:00Z',
}

const CLONE_QUEUED: CloneResponse = {
  repo_id: 'pallets__flask',
  full_name: 'pallets/flask',
  already_indexed: false,
  status: { ...READY_STATUS, stage: 'queued', progress: 0.01, message: 'Queued', is_ready: false, stats: null, metadata: null },
}

const CLONE_READY: CloneResponse = {
  repo_id: 'pallets__flask',
  full_name: 'pallets/flask',
  already_indexed: true,
  status: READY_STATUS,
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

export interface MockOptions {
  health?: HealthResponse
  /** Indexed repositories offered on the landing page. */
  repositories?: { repo_id: string; full_name: string; html_url: string; stage: string; indexed_at: string | null; total_chunks: number }[]
  /** `instant` jumps straight to the workspace; `progress` walks the stages. */
  cloneMode?: 'instant' | 'progress'
  /** Error injected into POST /clone. */
  cloneError?: { status: number; code: string; message: string }
  /** Terminal failure surfaced through GET /status. */
  statusFailure?: { code: string; message: string }
  ask?: AskResponse
  askError?: { status: number; code: string; message: string }
  /** Milliseconds POST /ask waits before answering (to observe the indicator). */
  askDelayMs?: number
  summary?: SummaryResponse
}

/**
 * Install API doubles for one page. Must be called before `page.goto`.
 */
export async function mockApi(page: Page, options: MockOptions = {}): Promise<void> {
  const {
    health = HEALTHY,
    repositories = [],
    cloneMode = 'instant',
    cloneError,
    statusFailure,
    ask = GROUNDED_ANSWER,
    askError,
    askDelayMs = 0,
    summary = SUMMARY,
  } = options

  let statusCall = 0

  await page.route('**/health', (route) => json(route, health))
  await page.route('**/repositories', (route) => json(route, { repositories }))

  await page.route('**/clone', (route) => {
    if (cloneError) {
      return json(route, { error: { code: cloneError.code, message: cloneError.message, hint: null } }, cloneError.status)
    }
    return json(route, cloneMode === 'instant' ? CLONE_READY : CLONE_QUEUED, 202)
  })

  await page.route('**/status*', (route) => {
    if (statusFailure) {
      return json(route, {
        ...READY_STATUS,
        stage: 'failed',
        progress: 1,
        is_ready: false,
        message: 'Indexing failed',
        error_code: statusFailure.code,
        error_message: statusFailure.message,
        stats: null,
      })
    }
    const step = PROGRESS_SEQUENCE[Math.min(statusCall, PROGRESS_SEQUENCE.length - 1)]
    statusCall += 1
    return json(route, step)
  })

  await page.route('**/ask', async (route) => {
    if (askDelayMs > 0) await new Promise((resolve) => setTimeout(resolve, askDelayMs))
    if (askError) {
      return json(route, { error: { code: askError.code, message: askError.message, hint: null } }, askError.status)
    }
    return json(route, ask)
  })

  await page.route('**/summary*', (route) => json(route, summary))
}

/** Drive the landing page all the way into the workspace. */
export async function openWorkspace(page: Page, options: MockOptions = {}): Promise<void> {
  await mockApi(page, options)
  await page.goto('/')
  await page.getByLabel('GitHub repository URL').fill('https://github.com/pallets/flask')
  await page.getByRole('button', { name: /index repository/i }).click()
  await page.getByRole('textbox', { name: 'Question' }).waitFor({ state: 'visible' })
}
