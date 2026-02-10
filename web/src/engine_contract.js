/**
 * 构建位图导出参数对象
 * 将前端使用的驼峰命名参数转换为后端引擎要求的下划线命名格式
 * 
 * @param {Object} params 包含导出参数的对象
 * @returns {Object} 符合后端接口规范的参数对象
 */
export const buildBitmapExportParams = ({
  imagePath,
  lutPath,
  nozzleWidthMm,
  targetWidthMm,
  nLayers,
  outputFormat,
  outDir,
  algo,
  smoothSigma,
  simplifyEps,
  autoBgRemove,
  bgTol,
  alphaThreshold,
  standard3mfPath,
  bambu3mfPath
}) => {
  const format = outputFormat || "stl";
  return {
    image_path: imagePath,
    lut_path: lutPath,
    nozzle_width_mm: Number(nozzleWidthMm),
    target_width_mm: Number(targetWidthMm),
    n_layers: Number(nLayers),
    algo: algo || "basic",
    smooth_sigma: smoothSigma !== undefined ? Number(smoothSigma) : undefined,
    simplify_eps: simplifyEps !== undefined ? Number(simplifyEps) : undefined,
    auto_bg_remove: autoBgRemove !== undefined ? Boolean(autoBgRemove) : undefined,
    bg_tol: bgTol !== undefined ? Number(bgTol) : undefined,
    alpha_threshold: alphaThreshold !== undefined ? Number(alphaThreshold) : undefined,
    output_format: format,
    export_3mf_standard: format === "3mf",
    export_3mf_bambu: format === "3mf",
    standard_3mf_path: standard3mfPath,
    bambu_3mf_path: bambu3mfPath,
    out_dir: outDir || undefined
  };
};

/**
 * 规范化位图处理结果
 * 将后端返回的下划线命名结果转换为前端使用的驼峰命名格式，并提供默认值
 * 
 * @param {Object} result 后端返回的原始结果
 * @returns {Object} 规范化后的结果对象
 */
export const normalizeBitmapResult = (result) => {
  const r = result || {};
  return {
    outDir: r.out_dir || "",
    stls: Array.isArray(r.stls) ? r.stls : [],
    standard3mf: r.standard_3mf || "",
    bambu3mf: r.bambu_3mf || "",
    meta: r.meta || "",
    preview2d: r.preview2d || ""
  };
};
