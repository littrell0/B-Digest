"""
字幕提取模块 - 通过 yt-dlp 下载并解析B站视频字幕
"""
import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from .video_info import SubtitleInfo

logger = logging.getLogger("bili_summarizer")


class SubtitleExtractor:
    """字幕提取器"""

    def __init__(self, cookie_file: Optional[Path] = None):
        """
        Args:
            cookie_file: 可选的cookie文件路径（用于需要登录的视频）
        """
        self.cookie_file = cookie_file

    def get_best_subtitle_lang(self, available: List[SubtitleInfo]) -> Optional[str]:
        """
        从可用字幕中选择最佳的中文字幕

        优先级: ai-zh > zh-Hans > zh-CN > zh > 其他含zh的

        Args:
            available: 可用字幕列表

        Returns:
            最佳字幕代码，如果没有中文字幕则返回 None
        """
        priority = ["ai-zh", "zh-Hans", "zh-CN", "zh"]

        for code in priority:
            for sub in available:
                if sub.code == code:
                    return code

        # 模糊匹配
        for sub in available:
            if "zh" in sub.code.lower() or "chinese" in sub.name.lower():
                return sub.code

        return None

    def download_subtitles(
        self,
        url: str,
        lang: str = "ai-zh",
        output_dir: Optional[Path] = None,
        timeout: int = 60,
    ) -> Optional[Path]:
        """
        下载视频字幕为 VTT 文件

        Args:
            url: B站视频URL
            lang: 字幕语言代码
            output_dir: 输出目录（默认为临时目录）
            timeout: 超时时间

        Returns:
            下载的 VTT 文件路径，失败返回 None
        """
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="bili_subs_"))
        output_dir.mkdir(parents=True, exist_ok=True)

        import yt_dlp

        output_template = str(output_dir / "%(title)s.%(ext)s")
        opts = {
            "writesubtitles": True,
            "subtitleslangs": [lang],
            "skip_download": True,
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
        }
        if self.cookie_file and self.cookie_file.exists():
            opts["cookiefile"] = str(self.cookie_file)

        logger.info("正在下载字幕 (lang=%s)...", lang)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            logger.error("字幕下载失败: %s", e)
            return None

        # 查找生成的文件
        for ext in ["*.vtt", "*.srt", "*.ass", "*.ssa"]:
            files = list(output_dir.glob(ext))
            if files:
                logger.info("字幕下载完成: %s", files[0].name)
                return files[0]

        logger.warning("字幕下载完成但未找到输出文件")
        return None

    def try_extract_subtitles(
        self,
        url: str,
        available_subs: List[SubtitleInfo],
        output_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        尝试提取字幕，自动选择最佳可用字幕

        Args:
            url: B站视频URL
            available_subs: 可用字幕列表
            output_dir: 输出目录

        Returns:
            VTT文件路径，失败返回 None
        """
        best_lang = self.get_best_subtitle_lang(available_subs)

        if best_lang is None:
            logger.info("未找到可用的中文字幕")
            return None

        logger.info("选择字幕: %s", best_lang)
        return self.download_subtitles(url, lang=best_lang, output_dir=output_dir)
