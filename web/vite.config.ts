import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({ mode }) => {
  // Anchor Vite to this project even when the workspace is accessed through a junction.
  const root = path.resolve(__dirname);
  const env = loadEnv(mode, root, "");
  const apiTarget = env.VITE_API_URL || "http://127.0.0.1:8001";
  return {
    root,
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: false,
      target: "es2020",
    },
  };
});
