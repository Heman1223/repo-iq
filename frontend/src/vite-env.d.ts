/// <reference types="vite/client" />

/** Typed environment variables consumed by the frontend. */
interface ImportMetaEnv {
  /** Base URL of the FastAPI backend, e.g. `http://127.0.0.1:8000`. */
  readonly VITE_API_BASE_URL?: string
  /** Axios timeout in milliseconds. */
  readonly VITE_API_TIMEOUT_MS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
