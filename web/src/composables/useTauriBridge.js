/**
 * Tauri 桥接组合式函数
 * 提供与 Tauri 后端交互的统一接口，并处理非 Tauri 环境（浏览器）的兼容性
 * 
 * @param {Function} t 国际化翻译函数
 * @returns {Object} 包含各种 Tauri API 的封装
 */
export const useTauriBridge = (t) => {
  // 获取 Tauri 核心 API
  const getTauriCore = () => window.__TAURI__?.core;
  // 获取 Tauri 事件 API
  const getTauriEvent = () => window.__TAURI__?.event;
  // 获取 Tauri 路径 API
  const getTauriPath = () => window.__TAURI__?.path;
  
  /**
   * 检查当前是否运行在 Tauri 环境中
   * @returns {boolean}
   */
  const hasTauri = () => Boolean(getTauriCore()?.invoke);

  /**
   * 调用 Tauri 后端指令
   * 
   * @param {string} cmd 指令名称
   * @param {Object} args 指令参数
   * @returns {Promise<any>} 后端返回的结果
   */
  const invoke = async (cmd, args) => {
    if (!hasTauri()) {
      const msg = t("toast.noTauri");
      console.warn(msg);
      throw new Error(msg);
    }
    return await getTauriCore().invoke(cmd, args);
  };

  /**
   * 监听 Tauri 后端发送的事件
   * 
   * @param {string} eventName 事件名称
   * @param {Function} handler 事件处理函数
   * @returns {Promise<Function>} 返回取消监听的函数
   */
  const listen = async (eventName, handler) => {
    if (!hasTauri()) {
      return () => {};
    }
    try {
      return await getTauriEvent().listen(eventName, handler);
    } catch (e) {
      console.error(t("toast.eventListenFail"), e);
      return () => {};
    }
  };

  /**
   * 打开系统原生文件/目录选择对话框
   * 
   * @param {Object} opts 对话框配置项
   * @returns {Promise<string|string[]|null>} 选择的路径
   */
  const openDialog = async (opts) => {
    if (!hasTauri()) {
      return null;
    }
    try {
      // 使用 dialog 插件的 invoke 调用
      return await getTauriCore().invoke("plugin:dialog|open", { options: opts || {} });
    } catch (e) {
      console.error("dialog 调用失败", e);
      return null;
    }
  };

  /**
   * 获取系统文档目录
   */
  const getDocumentsDir = async () => {
    if (!hasTauri()) return null;
    try {
      return await getTauriPath().documentDir();
    } catch (e) {
      console.error("获取文档目录失败", e);
      return null;
    }
  };

  /**
   * 获取应用本地数据目录 (AppData/Local)
   */
  const getLocalAppDataDir = async () => {
    if (!hasTauri()) return null;
    try {
      return await getTauriPath().appLocalDataDir();
    } catch (e) {
      console.error("获取本地应用数据目录失败", e);
      return null;
    }
  };

  /**
   * 拼接多个路径片段
   */
  const joinPaths = async (...parts) => {
    if (!hasTauri()) return parts.join("/");
    try {
      return await getTauriPath().join(...parts);
    } catch (e) {
      console.error("拼接路径失败", e);
      return parts.join("/");
    }
  };

  return {
    hasTauri,
    invoke,
    listen,
    openDialog,
    getDocumentsDir,
    getLocalAppDataDir,
    joinPaths
  };
};
