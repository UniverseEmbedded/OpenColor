"""
清单文件生成模块
用于在输出目录生成manifest.json，记录版本、时间戳、输入输出文件等信息
"""

import datetime
import json
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def write_manifest(output_dir, version, inputs=None, outputs=None, params=None):
    """
    在输出目录生成 manifest.json

    参数:
        output_dir: 输出目录路径
        version: 版本号
        inputs: 输入文件列表，默认为空列表
        outputs: 输出文件列表，默认为空列表
        params: 参数字典，默认为空字典

    返回:
        生成的manifest.json文件路径
    """
    manifest_path = Path(output_dir) / "manifest.json"

    data = {
        "version": version,
        "timestamp": datetime.datetime.now().isoformat(),
        "inputs": inputs or [],
        "outputs": outputs or [],
        "params": params or {},
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Manifest 已写入: {manifest_path}")
    return manifest_path
