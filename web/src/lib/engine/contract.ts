/**
 * 引擎通信协议定义
 * JSON-RPC 2.0 格式与 Python 引擎交互
 */

export interface JsonRpcRequest<T = unknown> {
  jsonrpc: "2.0";
  id: string;
  method: string;
  params: T;
}

export interface JsonRpcResponse<T = unknown> {
  jsonrpc: "2.0";
  id: string;
  result?: T;
  error?: {
    code: string;
    message: string;
    data?: unknown;
  };
}

export interface JobEvent<T = unknown> {
  event: "job.progress" | "job.done" | "job.error";
  job_id: string;
  progress?: number;
  stage?: string;
  message?: string;
  result?: T;
}

// 引擎方法名常量
export const ENGINE_METHODS = {
  PING: "ping",
  BITMAP_EXPORT: "bitmap.export",
  LUT_EXTRACT: "lut.extract",
  LUT_DETECT: "lut.detect",
  BOARD_GENERATE: "board.generate",
  DATASET_CREATE: "dataset.create",
  DATASET_ADD_OBSERVATION: "dataset.add_observation",
  DATASET_AGGREGATE: "dataset.aggregate",
  MCRT_VALIDATE: "mcrt.validate",
} as const;
