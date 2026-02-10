import { ref, computed } from "vue";

/**
 * 资源库管理组合式函数
 * 处理应用内的图片资源、导入和刷新等操作
 * 
 * @returns {Object} 资源库相关的状态和方法
 */
export const useLibrary = (invoke) => {
  // 资源库根目录路径
  const libraryRoot = ref("");
  // 资源列表
  const items = ref([]);
  // 加载状态
  const isLoading = ref(false);

  /**
   * 确保 items 是数组
   * @param {any} value 待检查的值
   */
  const normalizeItems = (value) => (Array.isArray(value) ? value : []);

  /**
   * 初始化资源库
   * 获取资源库根路径并执行初次刷新
   */
  const init = async () => {
    try {
      libraryRoot.value = await invoke("init_library");
      await refresh();
    } catch (e) {
      console.error("初始化资源库失败", e);
    }
  };

  /**
   * 刷新资源库内容
   * 从后端重新读取文件列表
   */
  const refresh = async () => {
    isLoading.value = true;
    try {
      const result = await invoke("list_library_files");
      items.value = normalizeItems(result);
    } catch (e) {
      console.error("刷新资源库失败", e);
      items.value = [];
    } finally {
      isLoading.value = false;
    }
  };

  /**
   * 导入文件到资源库
   * 将外部文件复制到资源库目录下并刷新列表
   *
   * @param {string} path 文件路径
   * @param {string} kind 文件类型: 'image' | 'spec' | 'profile'
   */
  const importFile = async (path, kind = 'image') => {
    if (!path) return;
    try {
      await invoke("import_to_library", { srcPath: path, kind });
      await refresh();
    } catch (e) {
      console.error("导入文件到资源库失败", e);
      throw e;
    }
  };

  /**
   * 根据类型获取过滤后的资源列表
   * @param {string} type 过滤类型，目前支持 'image'
   * @returns {Array} 过滤后的资源列表
   */
  const getFilteredItems = (type) => {
    if (type === "image") {
      return items.value.filter((item) =>
        ["png", "jpg", "jpeg", "webp"].includes(item.ext.toLowerCase())
      );
    }
    return items.value;
  };

  return {
    libraryRoot,
    items,
    isLoading,
    init,
    refresh,
    importFile,
    getFilteredItems,
  };
};
