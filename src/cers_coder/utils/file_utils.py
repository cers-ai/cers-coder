"""
文件处理工具
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional

import aiofiles


async def ensure_directory(path: str) -> Path:
    """确保目录存在"""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


async def read_file(file_path: str, encoding: str = 'utf-8') -> str:
    """异步读取文件"""
    async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
        return await f.read()


async def write_file(file_path: str, content: str, encoding: str = 'utf-8') -> None:
    """异步写入文件"""
    # 确保目录存在
    await ensure_directory(Path(file_path).parent)
    
    async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
        await f.write(content)


async def append_file(file_path: str, content: str, encoding: str = 'utf-8') -> None:
    """异步追加文件"""
    # 确保目录存在
    await ensure_directory(Path(file_path).parent)
    
    async with aiofiles.open(file_path, 'a', encoding=encoding) as f:
        await f.write(content)


def copy_file(src: str, dst: str) -> None:
    """复制文件"""
    # 确保目标目录存在
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_directory(src: str, dst: str) -> None:
    """复制目录"""
    if Path(dst).exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def get_file_size(file_path: str) -> int:
    """获取文件大小（字节）"""
    return Path(file_path).stat().st_size


def list_files(directory: str, pattern: str = "*", recursive: bool = False) -> List[Path]:
    """列出目录中的文件"""
    dir_path = Path(directory)
    if not dir_path.exists():
        return []
    
    if recursive:
        return list(dir_path.rglob(pattern))
    else:
        return list(dir_path.glob(pattern))


def clean_directory(directory: str, keep_patterns: Optional[List[str]] = None) -> None:
    """清理目录，保留指定模式的文件"""
    dir_path = Path(directory)
    if not dir_path.exists():
        return
    
    keep_patterns = keep_patterns or []
    
    for item in dir_path.iterdir():
        should_keep = False
        
        for pattern in keep_patterns:
            if item.match(pattern):
                should_keep = True
                break
        
        if not should_keep:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)


def get_relative_path(file_path: str, base_path: str) -> str:
    """获取相对路径"""
    return str(Path(file_path).relative_to(Path(base_path)))


def normalize_path(path: str) -> str:
    """标准化路径"""
    return str(Path(path).resolve())


def is_text_file(file_path: str) -> bool:
    """检查是否为文本文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)  # 读取前1024字符
        return True
    except (UnicodeDecodeError, IOError):
        return False


def get_file_extension(file_path: str) -> str:
    """获取文件扩展名"""
    return Path(file_path).suffix.lower()


def change_file_extension(file_path: str, new_extension: str) -> str:
    """更改文件扩展名"""
    path = Path(file_path)
    return str(path.with_suffix(new_extension))


def create_backup(file_path: str, backup_suffix: str = ".bak") -> str:
    """创建文件备份"""
    backup_path = file_path + backup_suffix
    copy_file(file_path, backup_path)
    return backup_path
