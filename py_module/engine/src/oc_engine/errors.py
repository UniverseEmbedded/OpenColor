"""统一错误模型和诊断包导出功能。

定义所有错误码、错误消息和诊断信息收集。
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ErrorInfo:
    """错误信息结构。"""

    code: str
    message: str
    suggestion: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


# 错误码定义
ERROR_CODES = {
    # 通用错误
    "E_INTERNAL": {
        "message": "引擎内部错误",
        "suggestion": "请查看控制台日志并联系开发者",
    },
    "E_BAD_REQUEST": {
        "message": "请求格式不正确",
        "suggestion": "请检查请求参数格式",
    },
    "E_METHOD": {
        "message": "未知方法",
        "suggestion": "请检查方法名称是否正确",
    },
    "E_BAD_PARAMS": {
        "message": "参数错误",
        "suggestion": "请检查参数是否完整且有效",
    },
    # 任务相关错误
    "E_JOB": {
        "message": "任务执行失败",
        "suggestion": "请检查输入文件和参数设置",
    },
    "E_CANCELLED": {
        "message": "任务已被取消",
        "suggestion": "任务已被用户取消",
    },
    # 文件相关错误
    "E_FILE_NOT_FOUND": {
        "message": "文件不存在",
        "suggestion": "请检查文件路径是否正确",
    },
    "E_FILE_READ": {
        "message": "文件读取失败",
        "suggestion": "请检查文件是否损坏或权限是否足够",
    },
    "E_FILE_WRITE": {
        "message": "文件写入失败",
        "suggestion": "请检查磁盘空间和写入权限",
    },
    # 参数相关错误
    "E_INVALID_PARAM": {
        "message": "参数无效",
        "suggestion": "请检查参数值是否在有效范围内",
    },
    "E_MISSING_PARAM": {
        "message": "缺少必需参数",
        "suggestion": "请提供所有必需的参数",
    },
    # 处理相关错误
    "E_PROCESSING": {
        "message": "处理失败",
        "suggestion": "请检查输入数据是否有效",
    },
    "E_EXPORT": {
        "message": "导出失败",
        "suggestion": "请检查输出目录和磁盘空间",
    },
}


def get_error_info(code: str, details: Optional[Dict[str, Any]] = None) -> ErrorInfo:
    """根据错误码获取错误信息。"""
    error_def = ERROR_CODES.get(code, ERROR_CODES["E_INTERNAL"])
    error_info = ErrorInfo(
        code=code,
        message=error_def["message"],
        suggestion=error_def["suggestion"],
        details=details or {},
    )
    return error_info


def collect_diagnostic_info() -> Dict[str, Any]:
    """收集诊断信息。"""
    return {
        "timestamp": datetime.now().isoformat(),
        "python_version": sys.version,
        "platform": sys.platform,
        "working_directory": os.getcwd(),
        "environment": dict(os.environ),
    }


def export_diagnostic_package(
    error_info: ErrorInfo,
    output_dir: str,
    extra_files: Optional[List[str]] = None,
) -> str:
    """导出诊断包。

    Args:
        error_info: 错误信息
        output_dir: 输出目录
        extra_files: 额外要包含的文件路径列表

    Returns:
        诊断包文件路径
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 生成诊断包文件名
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    diag_filename = f"diagnostic_{timestamp}.zip"
    diag_path = output_path / diag_filename

    import zipfile

    diagnostic_data = {
        "error": {
            "code": error_info.code,
            "message": error_info.message,
            "suggestion": error_info.suggestion,
            "details": error_info.details,
        },
        "diagnostics": collect_diagnostic_info(),
    }

    try:
        with zipfile.ZipFile(diag_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 添加诊断信息 JSON
            zf.writestr(
                "diagnostic_info.json",
                json.dumps(diagnostic_data, ensure_ascii=False, indent=2),
            )

            # 添加堆栈跟踪
            zf.writestr(
                "traceback.txt",
                traceback.format_exc(),
            )

            # 添加额外文件
            if extra_files:
                for file_path in extra_files:
                    file = Path(file_path)
                    if file.exists():
                        zf.write(file, file.name)
    except Exception as e:
        sys.stderr.write(f"[错误] 导出诊断包失败: {e}\n")
        sys.stderr.flush()
        raise

    return str(diag_path)


def log_error(error_info: ErrorInfo) -> None:
    """记录错误到控制台。"""
    sys.stderr.write(f"[错误] [{error_info.code}] {error_info.message}\n")
    if error_info.suggestion:
        sys.stderr.write(f"[建议] {error_info.suggestion}\n")
    if error_info.details:
        sys.stderr.write(
            f"[详情] {json.dumps(error_info.details, ensure_ascii=False)}\n"
        )
    sys.stderr.flush()
