// Vite配置文件
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { visualizer } from "rollup-plugin-visualizer";

export default defineConfig({
  plugins: [
    vue(),
    visualizer({
      open: false,
      filename: "stats.html",
      gzipSize: true,
      brotliSize: true,
    }),
  ],
  server: {
    host: true,
    port: 5173
  },
  test: {
    // Vitest 配置
    exclude: [
      'node_modules',
      'e2e/**/*', // 排除 Playwright E2E 测试
      'src-tauri/**/*', // 排除 Rust 代码
    ],
    include: [
      'test/**/*.{test,spec}.{js,ts}',
      'src/**/*.{test,spec}.{js,ts}',
    ],
    globals: true,
    environment: 'jsdom',
  },
});
