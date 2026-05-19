import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import node from "@astrojs/node";

export default defineConfig({
  output: "server",
  adapter: node({ mode: "standalone" }),
  integrations: [react()],
  server: {
    port: 3000,
    host: "0.0.0.0",
  },
  vite: {
    // Dev-server proxy only — in production the browser hits PUBLIC_API_URL directly.
    server: {
      proxy: {
        "/api": { target: "http://localhost:8000", changeOrigin: true },
      },
    },
  },
});
