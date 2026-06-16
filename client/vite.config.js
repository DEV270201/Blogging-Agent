import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI server allows CORS from http://localhost:5173 (Vite's default port).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
