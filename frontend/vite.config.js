import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_DEV_API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    base: env.VITE_ASSET_BASE || "/static/",
    plugins: [react()],
    build: {
      outDir: env.VITE_BUILD_OUT_DIR || "../frontend_build",
      assetsDir: "assets",
      emptyOutDir: true
    },
    server: {
      host: env.VITE_DEV_HOST || "127.0.0.1",
      port: Number(env.VITE_DEV_PORT || 3000),
      proxy: {
        "/api": proxyTarget,
        "/hunter": proxyTarget,
        "/media": proxyTarget,
        "/health": proxyTarget,
        "/ready": proxyTarget
      }
    },
    preview: {
      host: env.VITE_PREVIEW_HOST || "127.0.0.1",
      port: Number(env.VITE_PREVIEW_PORT || 4173)
    }
  };
});
