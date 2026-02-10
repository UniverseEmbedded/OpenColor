import { ref } from "vue";

/**
 * 消息提示 (Toast) 管理组合式函数
 * 处理全局消息提示的显示、内容更新和自动消失逻辑
 * 
 * @returns {Object} 包含 Toast 状态和控制方法的对象
 */
export const useToast = () => {
  // Toast 是否可见
  const toastVisible = ref(false);
  // Toast 主标题
  const toastTitle = ref("");
  // Toast 副标题或详细描述
  const toastSubtitle = ref("");
  // 用于自动隐藏的定时器引用
  let toastTimer = null;

  /**
   * 显示 Toast 消息
   * 
   * @param {string} title 主标题
   * @param {string} subtitle 副标题
   */
  const toastShow = (title, subtitle) => {
    toastTitle.value = title;
    toastSubtitle.value = subtitle;
    toastVisible.value = true;
    
    // 如果已有定时器，先清除
    if (toastTimer) clearTimeout(toastTimer);
    
    // 设置 2.2 秒后自动隐藏
    toastTimer = setTimeout(() => {
      toastVisible.value = false;
    }, 2200);
  };

  return {
    toastVisible,
    toastTitle,
    toastSubtitle,
    toastShow
  };
};
