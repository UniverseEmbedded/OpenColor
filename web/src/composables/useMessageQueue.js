import { ref, onMounted, onUnmounted } from 'vue';

/**
 * 全局消息队列
 * 用于处理引擎事件和跨组件通信
 */

// 全局状态 - 存储待处理的消息
const pendingMessages = ref([]);
const isProcessing = ref(false);

/**
 * 添加消息到队列
 * @param {string} type - 消息类型
 * @param {any} payload - 消息数据
 */
export function enqueueMessage(type, payload) {
  console.log(`[消息队列] 添加消息: ${type}`, payload);
  pendingMessages.value.push({
    type,
    payload,
    timestamp: Date.now(),
  });
  processQueue();
}

/**
 * 处理消息队列
 */
async function processQueue() {
  if (isProcessing.value) return;
  isProcessing.value = true;

  while (pendingMessages.value.length > 0) {
    const message = pendingMessages.value.shift();
    console.log(`[消息队列] 处理消息: ${message.type}`);

    // 触发全局事件
    window.dispatchEvent(new CustomEvent('mq-message', {
      detail: message
    }));

    // 触发特定类型事件
    window.dispatchEvent(new CustomEvent(`mq-${message.type}`, {
      detail: message.payload
    }));
  }

  isProcessing.value = false;
}

/**
 * 使用消息队列的组合式函数
 * @param {Object} options - 配置选项
 * @param {Function} options.onMessage - 消息处理回调
 * @param {string[]} options.types - 监听的消息类型
 */
export function useMessageQueue(options = {}) {
  const { onMessage, types = [] } = options;

  const handleMessage = (event) => {
    const message = event.detail;
    if (types.length === 0 || types.includes(message.type)) {
      onMessage?.(message);
    }
  };

  const handleSpecificMessages = {};

  onMounted(() => {
    // 监听通用消息事件
    window.addEventListener('mq-message', handleMessage);

    // 监听特定类型事件
    types.forEach(type => {
      const handler = (event) => {
        onMessage?.({ type, payload: event.detail, timestamp: Date.now() });
      };
      handleSpecificMessages[type] = handler;
      window.addEventListener(`mq-${type}`, handler);
    });

    // 检查是否有待处理的消息
    checkPendingMessages();
  });

  onUnmounted(() => {
    window.removeEventListener('mq-message', handleMessage);
    types.forEach(type => {
      if (handleSpecificMessages[type]) {
        window.removeEventListener(`mq-${type}`, handleSpecificMessages[type]);
      }
    });
  });

  /**
   * 检查是否有待处理的消息
   */
  function checkPendingMessages() {
    if (pendingMessages.value.length > 0) {
      processQueue();
    }
  }

  return {
    pendingMessages,
    checkPendingMessages,
  };
}

/**
 * 清空消息队列
 */
export function clearMessageQueue() {
  pendingMessages.value = [];
  console.log('[消息队列] 已清空');
}

/**
 * 获取队列长度
 */
export function getQueueLength() {
  return pendingMessages.value.length;
}
