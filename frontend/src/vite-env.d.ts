/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend base URL in production, e.g. https://your-api.onrender.com. Empty in dev. */
  readonly VITE_API_BASE?: string;
  /** Optional X-API-Token sent with REST requests (must match backend API_AUTH_TOKEN). */
  readonly VITE_API_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
