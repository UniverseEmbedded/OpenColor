// 应用程序入口文件
import { createApp } from "vue";
import App from "./App.vue";
import i18n from "./i18n";
import VueKonva from "vue-konva";
import "@tabler/icons-webfont/dist/tabler-icons.min.css"; // 导入图标字体
import "./styles.css"; // 导入全局样式
import { openUrl } from "@tauri-apps/plugin-opener";

const isTauriRuntime = () => Boolean((window as any)?.__TAURI__?.core?.invoke);

const normalizeHrefToExternalUrl = (href: string) => {
  const raw = href.trim();
  if (!raw) return null;
  if (raw.startsWith("#")) return null;
  if (raw.toLowerCase().startsWith("javascript:")) return null;

  const lower = raw.toLowerCase();
  const isSchemeAllowed =
    lower.startsWith("http://") ||
    lower.startsWith("https://") ||
    lower.startsWith("mailto:") ||
    lower.startsWith("tel:") ||
    lower.startsWith("//");
  if (!isSchemeAllowed) return null;

  try {
    if (raw.startsWith("//")) {
      return `${window.location.protocol}${raw}`;
    }
    return new URL(raw).toString();
  } catch {
    return null;
  }
};

const installExternalLinkGuard = () => {
  document.addEventListener(
    "click",
    async (e) => {
      if (!isTauriRuntime()) return;
      if (e.defaultPrevented) return;
      if (e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

      const path = (e.composedPath?.() ?? []) as Array<EventTarget>;
      const target = (path[0] ?? e.target) as HTMLElement | null;

      const anchor = target?.closest?.("a") as HTMLAnchorElement | null;
      if (!anchor) return;
      if (anchor.hasAttribute("download")) return;

      const href = anchor.getAttribute("href") ?? "";
      const url = normalizeHrefToExternalUrl(href);
      if (!url) return;

      e.preventDefault();
      e.stopPropagation();

      try {
        await openUrl(url);
      } catch (err) {
        console.error("打开外部链接失败", err, { url });
        try {
          window.open(url, "_blank", "noopener,noreferrer");
        } catch (err2) {
          console.error("使用浏览器兜底打开外部链接失败", err2, { url });
        }
      }
    },
    true,
  );
};

installExternalLinkGuard();

// 控制台日志自动保存功能
const setupConsoleLogCapture = () => {
  const logs: string[] = [];
  const maxLogs = 10000; // 最多保存10000条日志

  const captureLog = (level: string, args: any[]) => {
    const timestamp = new Date().toISOString();
    const message = args.map(arg => {
      if (typeof arg === 'object') {
        try {
          return JSON.stringify(arg);
        } catch {
          return String(arg);
        }
      }
      return String(arg);
    }).join(' ');
    const logEntry = `[${timestamp}] [${level}] ${message}`;
    logs.push(logEntry);
    
    // 限制日志数量
    if (logs.length > maxLogs) {
      logs.shift();
    }
  };

  // 拦截 console 方法
  const originalLog = console.log;
  const originalWarn = console.warn;
  const originalError = console.error;
  const originalInfo = console.info;
  const originalDebug = console.debug;

  console.log = (...args: any[]) => {
    captureLog('LOG', args);
    originalLog.apply(console, args);
  };

  console.warn = (...args: any[]) => {
    captureLog('WARN', args);
    originalWarn.apply(console, args);
  };

  console.error = (...args: any[]) => {
    captureLog('ERROR', args);
    originalError.apply(console, args);
  };

  console.info = (...args: any[]) => {
    captureLog('INFO', args);
    originalInfo.apply(console, args);
  };

  console.debug = (...args: any[]) => {
    captureLog('DEBUG', args);
    originalDebug.apply(console, args);
  };

  // 定期保存日志到文件（每30秒）
  const saveLogs = async () => {
    if (logs.length === 0) return;
    
    try {
      const logContent = logs.join('\n') + '\n';
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `localhost-${timestamp}.log`;
      
      // 在 Tauri 环境中保存到文件
      if (isTauriRuntime()) {
        const { writeTextFile, BaseDirectory } = await import('@tauri-apps/plugin-fs');
        await writeTextFile(filename, logContent, { baseDir: BaseDirectory.AppLog });
        console.log(`[日志] 已保存到 ${filename}`);
      } else {
        // 浏览器环境：下载文件
        const blob = new Blob([logContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      }
      
      // 清空已保存的日志
      logs.length = 0;
    } catch (err) {
      originalError.call(console, '[日志保存失败]', err);
    }
  };

  // 每30秒保存一次
  setInterval(saveLogs, 30000);

  // 页面卸载前保存
  window.addEventListener('beforeunload', () => {
    saveLogs();
  });

  // 暴露保存日志的方法到全局
  (window as any).saveConsoleLogs = saveLogs;
  (window as any).getConsoleLogs = () => logs.join('\n');
};

setupConsoleLogCapture();

// 创建并挂载 Vue 应用
createApp(App).use(i18n).use(VueKonva).mount("#app");
