"""
输入验证 + 通用工具模块
"""
import re
import sys
from typing import Optional


def ytdlp_cmd() -> list:
    """返回 yt-dlp 命令（兼容打包 exe 和开发环境）"""
    if getattr(sys, 'frozen', False):
        return [sys.executable, '-m', 'yt_dlp']
    return ['yt-dlp']


# B站视频URL正则模式
BILIBILI_URL_PATTERNS = [
    # bilibili.com/video/BV1xx411c7mD
    re.compile(r"https?://(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]+)"),
    # bilibili.com/video/av170001
    re.compile(r"https?://(?:www\.)?bilibili\.com/video/av(\d+)"),
    # b23.tv 短链接
    re.compile(r"https?://b23\.tv/([a-zA-Z0-9]+)"),
    # m.bilibili.com 移动端
    re.compile(r"https?://m\.bilibili\.com/video/(BV[a-zA-Z0-9]+)"),
    re.compile(r"https?://m\.bilibili\.com/video/av(\d+)"),
]


def validate_bilibili_url(url: str) -> bool:
    """
    验证是否为有效的B站视频链接

    Args:
        url: 用户输入的URL

    Returns:
        是否为合法的B站视频链接
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    for pattern in BILIBILI_URL_PATTERNS:
        if pattern.search(url):
            return True
    return False


def extract_bvid(url: str) -> Optional[str]:
    """
    从URL中提取BV号

    Args:
        url: B站视频URL

    Returns:
        BV号字符串，如果无法提取则返回 None
    """
    url = url.strip()
    for pattern in BILIBILI_URL_PATTERNS:
        match = pattern.search(url)
        if match:
            vid = match.group(1)
            if vid.startswith("BV"):
                return vid
            # AV号转BV号需要调用B站API，这里暂时返回AV号
            return f"av{vid}"
    return None


def validate_api_key(api_key: str) -> bool:
    """验证API Key格式（基本检查）"""
    return bool(api_key and len(api_key.strip()) >= 10)


def sanitize_filename(name: str) -> str:
    """
    清理文件名，移除不合法字符

    Args:
        name: 原始名称

    Returns:
        安全的文件名
    """
    # Windows 文件名不合法字符
    illegal_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(illegal_chars, "_", name)
    # 移除首尾空格和点
    sanitized = sanitized.strip(". ")
    # 限制长度
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized or "untitled"
