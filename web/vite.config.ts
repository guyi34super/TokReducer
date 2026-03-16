import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": "http://localhost:8080",
      "/v1": "http://localhost:8080",
      "/health": "http://localhost:8080",
      "/compress": "http://localhost:8080",
      "/decompress": "http://localhost:8080",
      "/chat": "http://localhost:8080",
    },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom", "react-router-dom"],
          firebase: ["firebase/app", "firebase/auth"],
        },
      },
    },
  },
});
