from __future__ import annotations


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
"""
原子性 IO 操作工具。
提供确保文件写入和 ZIP 创建原子性的函数，防止产生损坏的部分文件。
"""

# 导入操作系统相关模块
import os
# 导入 ZIP 文件处理模块
import zipfile
# 导入路径处理模块
from pathlib import Path
# 导入类型提示模块
from typing import Callable


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """
    使用临时文件将字节数据原子性地写入路径。
    
    参数:
        path: 目标文件路径
        data: 要写入的字节数据
    
    注意:
        使用临时文件和重命名来保证原子性，
        确保写入过程中不会出现部分写入的文件。
        如果发生错误，临时文件将被清理。
    """
    # 创建临时文件路径
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        # 写入数据到临时文件
        temp_path.write_bytes(data)
        # 如果目标文件已存在，则删除
        if path.exists():
            os.remove(path)
        # 原子性地重命名临时文件为目标文件
        os.rename(temp_path, path)
    except Exception as e:
        # 如果发生异常，清理临时文件并重新抛出异常
        if temp_path.exists():
            os.remove(temp_path)
        logger.error(f"原子性写入失败: {e}")
        raise

def atomic_zip_create(path: Path, write_func: Callable[[zipfile.ZipFile], None]) -> None:
    """
    原子性地创建 ZIP 文件。
    
    参数:
        path: 目标 ZIP 文件路径
        write_func: 写入函数，接收 ZipFile 对象作为参数
    
    注意:
        使用临时文件和重命名来保证原子性，
        确保写入过程中不会出现部分写入的文件。
        如果发生错误，临时文件将被清理。
    """
    # 创建临时文件路径
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        # 打开临时 ZIP 文件并调用写入函数
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            write_func(zf)
        
        # 如果目标文件已存在，则删除
        if path.exists():
            os.remove(path)
        # 原子性地重命名临时文件为目标文件
        os.rename(temp_path, path)
    except Exception as e:
        # 如果发生异常，清理临时文件并重新抛出异常
        if temp_path.exists():
            os.remove(temp_path)
        logger.error(f"原子性创建 ZIP 失败: {e}")
        raise
