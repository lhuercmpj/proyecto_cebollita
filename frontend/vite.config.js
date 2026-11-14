import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Puerto fijo distinto del de Docker (5173), para poder tener ambos encendidos.
  server: { port: 5174, strictPort: true },
});
