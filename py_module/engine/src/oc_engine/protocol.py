from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

# 协议版本号
PROTOCOL_VERSION = "1.0.0"
# 引擎版本号
ENGINE_VERSION = "0.1.0"


def write_json_line(obj: Dict[str, Any]) -> None:
    """
    将字典对象序列化为 JSON 并写入标准输出
    
    @param obj: 要输出的字典对象
    """
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception as e:
        sys.stderr.write(f"[错误] JSON 序列化失败: {e}\n")
        sys.stderr.flush()
        return
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def make_response(id_: str, result: Any) -> Dict[str, Any]:
    """
    创建 JSON-RPC 响应对象
    
    @param id_: 请求 ID
    @param result: 响应结果数据
    @return: JSON-RPC 响应字典
    """
    return {
        "jsonrpc": "2.0",
        "protocol_version": PROTOCOL_VERSION,
        "engine_version": ENGINE_VERSION,
        "id": id_,
        "result": result
    }


def make_event_progress(job_id: str, progress: float, stage: str, message: str) -> Dict[str, Any]:
    """
    创建任务进度事件
    
    @param job_id: 任务 ID
    @param progress: 进度值（0.0 - 1.0）
    @param stage: 当前阶段名称
    @param message: 进度消息
    @return: 进度事件字典
    """
    return {
        "event": "job.progress",
        "protocol_version": PROTOCOL_VERSION,
        "job_id": job_id,
        "progress": float(progress),
        "stage": stage,
        "message": message
    }


def make_event_done(job_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    创建任务完成事件
    
    @param job_id: 任务 ID
    @param result: 任务结果数据
    @return: 完成事件字典
    """
    return {
        "event": "job.done",
        "protocol_version": PROTOCOL_VERSION,
        "job_id": job_id,
        "result": result
    }


def make_event_error(job_id: str, code: str, message: str) -> Dict[str, Any]:
    """
    创建任务错误事件
    
    @param job_id: 任务 ID
    @param code: 错误代码
    @param message: 错误消息
    @return: 错误事件字典
    """
    return {
        "event": "job.error",
        "protocol_version": PROTOCOL_VERSION,
        "job_id": job_id,
        "code": code,
        "message": message
    }


def parse_json_line(line: str) -> Optional[Dict[str, Any]]:
    """
    解析 JSON 行数据
    
    @param line: JSON 字符串
    @return: 解析后的字典，解析失败返回 None
    """
    try:
        return json.loads(line)
    except Exception as e:
        sys.stderr.write(f"[错误] 无法解析 JSON 行: {e}\n")
        sys.stderr.flush()
        return None
