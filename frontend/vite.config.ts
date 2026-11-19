import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The browser only talks to Vite on 5173. Anything under /api is forwarded to uvicorn on
// 8000 (or KAIZEN_API_PORT) with the /api part removed, so /api/issues reaches the back end's /issues. That
// keeps the back end free of CORS settings, and it stops a page reload on /issues/3 from
// being sent to the API instead of the app.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: `http://localhost:${(globalThis as unknown as { process: { env: Record<string, string | undefined> } }).process.env.KAIZEN_API_PORT ?? "8000"}`,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
