"""
输出写入模块 - 生成 Markdown 格式的逐字稿和概述
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils.validators import sanitize_filename

logger = logging.getLogger("bili_summarizer")


@dataclass
class OutputPaths:
    """输出文件路径"""
    output_dir: Path
    transcript_file: Path
    summary_file: Path


class OutputWriter:
    """Markdown 输出写入器"""

    def __init__(self, output_base_dir: Path):
        """
        Args:
            output_base_dir: 输出根目录
        """
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

    def write_transcript(
        self,
        video_title: str,
        transcript: str,
        video_url: str,
        duration: str = "",
        source: str = "字幕提取",
        uploader: str = "",
        fmt: str = "md",
    ) -> Path:
        """写入逐字稿文件"""
        output_dir = self._get_video_output_dir(video_title, uploader)
        output_dir.mkdir(parents=True, exist_ok=True)

        ext = "txt" if fmt == "txt" else "md"
        file_path = output_dir / f"transcript.{ext}"

        if fmt == "txt":
            header = f"逐字稿: {video_title}\n"
            header += f"视频链接: {video_url}\n"
            if uploader:
                header += f"UP主: {uploader}\n"
            if duration:
                header += f"视频时长: {duration}\n"
            header += f"字幕来源: {source}\n"
            header += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += "=" * 40 + "\n\n"
            content = header + transcript
        else:
            metadata_lines = [
                f"# 逐字稿: {video_title}", "",
                f"- **视频链接**: {video_url}",
                f"- **UP主**: {uploader}" if uploader else "",
                f"- **视频时长**: {duration}" if duration else "",
                f"- **字幕来源**: {source}",
                f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "", "---", "",
            ]
            metadata = "\n".join(l for l in metadata_lines if l)
            content = metadata + "\n\n" + transcript

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def write_summary(
        self,
        video_title: str,
        summary: str,
        video_url: str,
        duration: str = "",
        model_name: str = "DeepSeek",
        uploader: str = "",
        fmt: str = "md",
    ) -> Path:
        """写入AI概述文件"""
        output_dir = self._get_video_output_dir(video_title, uploader)
        output_dir.mkdir(parents=True, exist_ok=True)

        ext = "txt" if fmt == "txt" else "md"
        file_path = output_dir / f"summary.{ext}"

        if fmt == "txt":
            header = f"AI概述: {video_title}\n"
            header += f"视频链接: {video_url}\n"
            if uploader:
                header += f"UP主: {uploader}\n"
            if duration:
                header += f"视频时长: {duration}\n"
            header += f"生成模型: {model_name}\n"
            header += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += "=" * 40 + "\n\n"
            content = header + summary
        else:
            metadata_lines = [
                f"# AI概述: {video_title}", "",
                f"- **视频链接**: {video_url}",
                f"- **UP主**: {uploader}" if uploader else "",
                f"- **视频时长**: {duration}" if duration else "",
                f"- **生成模型**: {model_name}",
                f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "", "---", "",
            ]
            metadata = "\n".join(l for l in metadata_lines if l)
            content = metadata + "\n\n" + summary

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def write_all(
        self,
        video_title: str,
        transcript: str,
        summary: str,
        video_url: str,
        duration: str = "",
        source: str = "字幕提取",
        model_name: str = "DeepSeek",
        uploader: str = "",
        fmt: str = "md",
    ) -> OutputPaths:
        """
        写入所有输出文件

        Returns:
            OutputPaths 包含所有输出文件路径
        """
        output_dir = self._get_video_output_dir(video_title, uploader)

        transcript_path = self.write_transcript(
            video_title=video_title, transcript=transcript,
            video_url=video_url, duration=duration,
            source=source, uploader=uploader, fmt=fmt,
        )
        summary_path = self.write_summary(
            video_title=video_title, summary=summary,
            video_url=video_url, duration=duration,
            model_name=model_name, uploader=uploader, fmt=fmt,
        )

        return OutputPaths(
            output_dir=output_dir,
            transcript_file=transcript_path,
            summary_file=summary_path,
        )

    def _get_video_output_dir(self, video_title: str, uploader: str = "") -> Path:
        """获取视频的输出目录: output/<UP主>/<视频标题>/"""
        if uploader:
            safe_uploader = sanitize_filename(uploader)
            safe_title = sanitize_filename(video_title)
            return self.output_base_dir / safe_uploader / safe_title
        safe_title = sanitize_filename(video_title)
        return self.output_base_dir / safe_title
