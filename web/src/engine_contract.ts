// 用于构建引擎请求参数和规范化响应的类型定义
// 该文件应与 py_module/engine/src/oc_engine/schema.py 保持同步

export interface JsonRpcRequest<T = any> {
  jsonrpc: "2.0";
  id: string;
  method: string;
  params: T;
}

export interface JsonRpcResponse<T = any> {
  jsonrpc: "2.0";
  id: string;
  result?: T;
  error?: {
    code: string;
    message: string;
    data?: any;
  };
}

export interface JobEvent<T = any> {
  event: "job.progress" | "job.done" | "job.error";
  job_id: string;
  progress?: number;
  stage?: string;
  message?: string;
  result?: T;
}

export interface HealthPingResult {
  status: string;
  version: string;
  timestamp: number;
}

export interface BoardGenerateParams {
  out_dir?: string;
  color_system?: string;
  n_layers?: number;
  cell_size_mm?: number;
  layer_height_mm?: number;
  total_cells?: number;
  data_cells?: number;
  export_format?: string;
  export_formats?: string[];
}

export interface BoardExportParams {
  spec_path: string;
  out_dir?: string;
  export_format?: string;
  export_formats?: string[];
}

export interface LutExtractParams {
  photo_path: string;
  recipes_path: string;
  out_dir?: string;
}

export interface LutDetectParams {
  photo_path: string;
  out_dir?: string;
}

export interface BitmapExportParams {
  image_path: string;
  lut_path: string;
  nozzle_width_mm?: number;
  target_width_mm?: number;
  n_layers?: number;
  output_format?: string;
  out_dir?: string;
}

export interface SvgExportParams {
  svg_path: string;
  width_mm?: number;
  thickness_mm?: number;
  tol_mm?: number;
  simplify_mm?: number;
  min_area_mm2?: number;
  palette_mode?: string;
  palette_tol?: number;
  out_dir?: string;
}

export interface JobManifest {
  job_id: string;
  kind: string;
  out_dir: string;
  created_at: number;
  artifacts: Record<string, string | string[]>;
  plate_info?: Record<string, any>;
  materials: Array<Record<string, any>>;
  metadata: Record<string, any>;
}

// 响应结果定义
export interface BitmapResult {
  out_dir: string;
  meta: string;
  stls: string[];
  preview2d?: string;
  preview3d?: string;
  standard_3mf?: string;
  bambu_3mf?: string;
}

export interface SvgResult {
  out_dir: string;
  meta: string;
  stls: string[];
  standard_3mf?: string;
  bambu_3mf?: string;
}

export interface BoardGenerateResult {
  out_dir: string;
  board_spec_path: string;
  standard_3mf?: string;
  stls: string[];
  preview: string;
  meta: string;
}

export interface BoardExportResult {
  out_dir: string;
  spec_path: string;
  standard_3mf?: string;
  stls: string[];
}
