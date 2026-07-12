"""
字幕提取模块 - 通过 yt-dlp 下载并解析B站视频字幕
"""
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from src.utils.validators import ytdlp_cmd
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

        # yt-dlp 字幕下载模板
        output_template = output_dir / "%(title)s.%(ext)s"

        cmd = ytdlp_cmd() + [
            "--write-subs",
            "--sub-langs", lang,
            "--skip-download",
            "--no-playlist",
            "--convert-subs", "vtt",
            "-o", str(output_template),
        ]

        if self.cookie_file and self.cookie_file.exists():
            cmd.extend(["--cookies", str(self.cookie_file)])

        cmd.append(url)

        logger.info("正在下载字幕 (lang=%s)...", lang)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
            )
        except subprocess.TimeoutExpired:
            logger.error("字幕下载超时 (%ds)", timeout)
            return None

        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.error("字幕下载失败: %s", stderr)
            return None

        # 查找生成的 VTT 文件
        vtt_files = list(output_dir.glob("*.vtt"))
        if vtt_files:
            vtt_path = vtt_files[0]
            logger.info("字幕下载完成: %s", vtt_path.name)
            return vtt_path

        # 可能下载为其他格式
        for ext in ["*.srt", "*.ass", "*.ssa"]:
            files = list(output_dir.glob(ext))
            if files:
                logger.info("字幕下载完成 (非VTT格式): %s", files[0].name)
                return files[0]

        logger.warning("字幕下载完成但未找到输出文件")

        # 打印输出以帮助调试
        logger.debug("stdout: %s", result.stdout)
        logger.debug("stderr: %s", result.stderr)

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
