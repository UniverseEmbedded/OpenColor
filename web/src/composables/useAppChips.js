import { computed } from "vue";

/**
 * 应用程序状态标签 (Chips) 组合式函数
 * 用于根据当前的输入、配置和输出设置生成对应的显示文本
 * 
 * @param {Object} params
 * @param {Function} params.t - 国际化翻译函数
 * @param {Ref} params.inputPath - 输入文件路径的响应式引用
 * @param {Ref} params.inputKind - 输入文件类型的响应式引用 (svg/png/mixed)
 * @param {Ref} params.selectedProfileKey - 当前选择的配置方案 Key
 * @param {Ref} params.outputFormat - 输出格式 (stl/3mf)
 */
export const useAppChips = ({ t, inputPath, inputKind, selectedProfileKey, outputFormat }) => {
  /**
   * 计算输入状态的标签文本
   */
  const chipInput = computed(() => {
    if (!inputPath.value) return t("chip.noInput");
    if (inputKind.value === "svg") return t("chip.inputPrefix") + t("chip.inputSvg");
    if (inputKind.value === "png") return t("chip.inputPrefix") + t("chip.inputPng");
    return t("chip.inputPrefix") + t("chip.inputMixed");
  });

  /**
   * 计算当前配置方案的标签文本
   */
  const chipProfile = computed(() => t(`option.${selectedProfileKey.value}`));

  /**
   * 计算输出格式的标签文本
   */
  const chipOutput = computed(() => {
    if (outputFormat.value === "stl") return t("chip.outputPrefix") + t("chip.outputStl");
    return t("chip.outputPrefix") + t("chip.output3mf");
  });

  return {
    chipInput,
    chipProfile,
    chipOutput
  };
};
