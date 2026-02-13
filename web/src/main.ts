import "./app.css";
import { mount } from "svelte";
import Layout from "./routes/+layout.svelte";
import { getTauriBridge } from "$lib/tauri/bridge";

function formatTimestamp(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  const yyyy = date.getFullYear();
  const mm = pad(date.getMonth() + 1);
  const dd = pad(date.getDate());
  const hh = pad(date.getHours());
  const mi = pad(date.getMinutes());
  const ss = pad(date.getSeconds());
  return `${yyyy}-${mm}-${dd}][${hh}:${mi}:${ss}`;
}

function getLevelLabel(level: string) {
  if (level === "ERROR") {
    return "错误";
  }
  if (level === "WARN") {
    return "警告";
  }
  if (level === "DEBUG") {
    return "调试";
  }
  return "信息";
}

function stringifyLogArg(arg: unknown) {
  if (arg instanceof Error) {
    return arg.stack || `${arg.name}: ${arg.message}`;
  }
  if (typeof arg === "string") {
    return arg;
  }
  try {
    return JSON.stringify(arg);
  } catch {
    return String(arg);
  }
}

function formatLogMessage(level: string, args: unknown[]) {
  const levelLabel = getLevelLabel(level);
  const body = args.map(stringifyLogArg).join(" ");
  return `[前端][${levelLabel}] ${body}`;
}

async function setupUiLogForwarding() {
  const bridge = getTauriBridge();
  if (!bridge.hasTauri) {
    return;
  }
  try {
    const logPluginPromise = import("@tauri-apps/plugin-log");
    const originalConsole = {
      log: console.log,
      info: console.info,
      warn: console.warn,
      error: console.error,
      debug: console.debug
    };

    const forward = async (level: string, args: unknown[]) => {
      const message = formatLogMessage(level, args);
      try {
        const logPlugin = await logPluginPromise;
        if (level === "ERROR") {
          await logPlugin.error(message);
          return;
        }
        if (level === "WARN") {
          await logPlugin.warn(message);
          return;
        }
        if (level === "DEBUG") {
          await logPlugin.debug(message);
          return;
        }
        await logPlugin.info(message);
      } catch (e) {
        originalConsole.error("[日志] 转发失败:", e);
      }
    };

    console.log = (...args: unknown[]) => {
      const timestamp = formatTimestamp(new Date());
      originalConsole.log(`[${timestamp}][${getLevelLabel("INFO")}]`, ...args);
      void forward("INFO", args);
    };
    console.info = (...args: unknown[]) => {
      const timestamp = formatTimestamp(new Date());
      originalConsole.info(`[${timestamp}][${getLevelLabel("INFO")}]`, ...args);
      void forward("INFO", args);
    };
    console.warn = (...args: unknown[]) => {
      const timestamp = formatTimestamp(new Date());
      originalConsole.warn(`[${timestamp}][${getLevelLabel("WARN")}]`, ...args);
      void forward("WARN", args);
    };
    console.error = (...args: unknown[]) => {
      const timestamp = formatTimestamp(new Date());
      originalConsole.error(`[${timestamp}][${getLevelLabel("ERROR")}]`, ...args);
      void forward("ERROR", args);
    };
    console.debug = (...args: unknown[]) => {
      const timestamp = formatTimestamp(new Date());
      originalConsole.debug(`[${timestamp}][${getLevelLabel("DEBUG")}]`, ...args);
      void forward("DEBUG", args);
    };
  } catch (e) {
    console.error("[日志] 初始化转发失败:", e);
  }
}

void setupUiLogForwarding();

// 使用Svelte 5的mount函数挂载组件
const app = mount(Layout, {
  target: document.getElementById("app")!,
});

console.log("[启动] Svelte 5 应用已启动");

const initialLoading = document.querySelector('#loading-screen[data-initial="true"]');
if (initialLoading) {
  initialLoading.remove();
}

export default app;
