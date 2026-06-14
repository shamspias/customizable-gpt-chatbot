import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    // Proxy API + SSE to the FastAPI app so the browser sees same-origin (no CORS).
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
