"""
视频信息提取模块 - 通过 yt-dlp 获取B站视频元数据
"""
import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.utils.validators import ytdlp_cmd

logger = logging.getLogger("bili_summarizer")


@dataclass
class SubtitleInfo:
    """字幕轨道信息"""
    language: str
    code: str           # 如 "zh-Hans", "ai-zh"
    name: str           # 如 "中文（自动生成）"
    is_auto: bool       # 是否为AI自动生成


@dataclass
class VideoInfo:
    """视频元数据"""
    title: str
    url: str
    bvid: str = ""
    duration: int = 0          # 秒
    uploader: str = ""
    upload_date: str = ""      # YYYYMMDD
    description: str = ""
    thumbnail: str = ""
    subtitles: List[SubtitleInfo] = field(default_factory=list)
    raw_json: dict = field(default_factory=dict)

    @property
    def duration_str(self) -> str:
        """格式化的时长字符串"""
        h, m = divmod(self.duration, 3600)
        m, s = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @property
    def has_ai_subtitles(self) -> bool:
        """是否有AI中文字幕"""
        return any(
            sub.code in ("ai-zh", "zh-Hans", "zh-CN", "zh")
            for sub in self.subtitles
        )


def extract_video_info(
    url: str,
    cookie_file: Optional[Path] = None,
    timeout: int = 30,
) -> VideoInfo:
    """
    通过 yt-dlp 提取视频信息

    Args:
        url: B站视频URL
        cookie_file: 可选的cookie文件路径
        timeout: 超时时间（秒）

    Returns:
        VideoInfo 对象

    Raises:
        subprocess.TimeoutExpired: yt-dlp 超时
        RuntimeError: yt-dlp 执行失败
    """
    cmd = ytdlp_cmd() + [
        "--dump-json",
        "--no-playlist",
        "--no-download",
    ]

    if cookie_file and cookie_file.exists():
        cmd.extend(["--cookies", str(cookie_file)])

    cmd.append(url)

    logger.info("正在提取视频信息: %s", url)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp 提取视频信息超时 (%ds)", timeout)
        raise
    except FileNotFoundError:
        logger.error("未找到 yt-dlp，请先安装: pip install yt-dlp")
        raise RuntimeError("yt-dlp 未安装，请运行: pip install yt-dlp")

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "未知错误"
        logger.error("yt-dlp 执行失败: %s", error_msg)
        raise RuntimeError(f"视频信息提取失败: {error_msg}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error("yt-dlp 返回数据解析失败: %s", e)
        raise RuntimeError("视频信息解析失败")

    # 构建 VideoInfo
    subtitles = _parse_subtitles(data)
    bvid = _extract_bvid(data, url)

    video_info = VideoInfo(
        title=data.get("title", "未知标题"),
        url=url,
        bvid=bvid,
        duration=int(data.get("duration", 0)),
        uploader=data.get("uploader", data.get("channel", "未知UP主")),
        upload_date=data.get("upload_date", ""),
        description=data.get("description", ""),
        thumbnail=data.get("thumbnail", ""),
        subtitles=subtitles,
        raw_json=data,
    )

    logger.info("视频信息提取完成: %s (BV%s)", video_info.title, video_info.bvid)
    logger.info("  时长: %s, UP主: %s", video_info.duration_str, video_info.uploader)
    if subtitles:
        sub_names = [s.name for s in subtitles]
        logger.info("  字幕: %s", ", ".join(sub_names))

    return video_info


def _parse_subtitles(data: dict) -> List[SubtitleInfo]:
    """从 yt-dlp JSON 输出中解析字幕信息"""
    subtitles = []

    # yt-dlp 可能将字幕信息放在不同字段
    sub_data = data.get("subtitles", {}) or data.get("automatic_captions", {})

    for lang_code, tracks in sub_data.items():
        if not tracks:
            continue

        track = tracks[0]  # 取第一个轨道
        name = track.get("name", lang_code)
        is_auto = "auto" in name.lower() or "自动" in name or lang_code.startswith("ai-")

        subtitles.append(SubtitleInfo(
            language=lang_code,
            code=lang_code,
            name=name,
            is_auto=is_auto,
        ))

    return subtitles


def _extract_bvid(data: dict, url: str) -> str:
    """从数据或URL中提取BV号"""
    # 尝试从数据中获取
    bvid = data.get("id", "")
    if bvid and bvid.startswith("BV"):
        return bvid

    # 尝试从URL模式中获取
    for field in ["display_id", "webpage_url_basename"]:
        val = data.get(field, "")
        if val and val.startswith("BV"):
            return val

    # 从URL解析
    import re
    match = re.search(r"BV([a-zA-Z0-9]+)", url)
    if match:
        return f"BV{match.group(1)}"

    match = re.search(r"av(\d+)", url, re.IGNORECASE)
    if match:
        return f"av{match.group(1)}"

    return bvid or "unknown"


def list_subtitles(
    url: str,
    cookie_file: Optional[Path] = None,
    timeout: int = 30,
) -> List[SubtitleInfo]:
    """
    列出视频可用的所有字幕

    Args:
        url: B站视频URL
        cookie_file: 可选的cookie文件路径
        timeout: 超时时间

    Returns:
        字幕信息列表
    """
    cmd = ytdlp_cmd() + [
        "--list-subs",
        "--no-playlist",
        "--no-download",
    ]

    if cookie_file and cookie_file.exists():
        cmd.extend(["--cookies", str(cookie_file)])

    cmd.append(url)

    logger.info("正在获取字幕列表...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        logger.error("获取字幕列表超时")
        return []

    # 从 yt-dlp 输出中解析字幕
    subtitles = []
    in_sub_section = False

    for line in result.stdout.split("\n") + result.stderr.split("\n"):
        line = line.strip()

        if "Available subtitles" in line or "subtitles for" in line:
            in_sub_section = True
            continue
        if "Available automatic captions" in line:
            in_sub_section = True
            continue
        if in_sub_section and line.startswith(("Language", "formats", "has")):
            continue
        if in_sub_section and not line:
            continue

    # 更可靠的方式是直接用 --dump-json
    info = extract_video_info(url, cookie_file, timeout)
    return info.subtitles
