"""
视频信息提取模块 - 通过 yt-dlp 获取B站视频元数据
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

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
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "no-playlist": True,
        "extract_flat": False,
    }
    if cookie_file and cookie_file.exists():
        opts["cookiefile"] = str(cookie_file)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
    except Exception as e:
        logger.error("yt-dlp 提取失败: %s", e)
        raise RuntimeError(f"视频信息提取失败: {e}")

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
    """列出视频可用的所有字幕（复用 extract_video_info）"""
    info = extract_video_info(url, cookie_file, timeout)
    return info.subtitles
