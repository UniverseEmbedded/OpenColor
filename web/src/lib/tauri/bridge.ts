/**
 * Tauri API 桥接
 * 封装与 Rust 后端的通信
 */

import { invoke as tauriInvoke } from "@tauri-apps/api/core";
import { listen as tauriListen } from "@tauri-apps/api/event";
import { revealItemInDir } from "@tauri-apps/plugin-opener";

// 使用普通变量替代 $state
let hasTauri = false;

// 检测是否在 Tauri 环境中
if (typeof window !== "undefined" && (window as any).__TAURI__) {
  hasTauri = true;
}

export function getTauriBridge() {
  return {
    get hasTauri() { return hasTauri; },

    async invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
      if (!hasTauri) {
        throw new Error("不在 Tauri 环境中");
      }
      return tauriInvoke(cmd, args);
    },

    async listen<T>(event: string, handler: (payload: T) => void) {
      if (!hasTauri) {
        throw new Error("不在 Tauri 环境中");
      }
      return tauriListen(event, (e) => handler(e.payload as T));
    },

    /**
     * 在资源管理器中显示指定路径
     */
    async revealInExplorer(path: string) {
      if (!hasTauri) {
        throw new Error("不在 Tauri 环境中");
      }
      return revealItemInDir(path);
    },
  };
}
