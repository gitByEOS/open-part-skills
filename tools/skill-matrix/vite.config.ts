import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // 相对路径：本地 tools 下 http.server 与 GitHub Pages 子目录均可加载资源
  base: "./",
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5176,
    strictPort: true,
  },
});
