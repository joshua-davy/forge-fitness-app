/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}

interface Window {
  __FORGE_API_URL__?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
