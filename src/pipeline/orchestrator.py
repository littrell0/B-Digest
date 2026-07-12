"""
管线编排器 - 协调整个处理流程
"""
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from src.config import Config
from src.pipeline.video_info import VideoInfo, extract_video_info
from src.pipeline.subtitle_extractor import SubtitleExtractor
from src.pipeline.summarizer import AISummarizer
from src.pipeline.asr_engine import ASREngine, ASRCancelledError
from src.pipeline.output_writer import OutputPaths, OutputWriter
from src.utils.text_utils import parse_vtt_to_text, parse_srt_to_text

logger = logging.getLogger("bili_summarizer")


@dataclass
class ProcessResult:
    """处理结果"""
    video_title: str = ""
    video_url: str = ""
    bvid: str = ""
    transcript: str = ""
    summary: str = ""
    output_dir: Optional[Path] = None
    transcript_file: Optional[Path] = None
    summary_file: Optional[Path] = None
    source: str = ""           # "subtitles" 或 "asr"
    error: Optional[str] = None
    cancelled: bool = False
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return self.error is None


class PipelineManager:
    """处理管线编排器"""

    def __init__(
        self,
        config: Config,
        progress_callback: Optional[Callable] = None,
    ):
        self.config = config
        self.progress_callback = progress_callback
        self.subtitle_extractor = SubtitleExtractor()
        self._output_writer: Optional[OutputWriter] = None
        self._cancel_event = threading.Event()

    @property
    def output_writer(self) -> OutputWriter:
        if self._output_writer is None:
            self._output_writer = OutputWriter(Path(self.config.output_dir))
        return self._output_writer

    def cancel(self):
        """取消当前处理"""
        logger.info("用户请求取消处理")
        self._cancel_event.set()

    def reset(self):
        """重置取消状态"""
        self._cancel_event.clear()

    def _is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _report_progress(self, step: str, percent: int, message: str = ""):
        logger.info("[%d%%] %s: %s", percent, step, message or step)
        if self.progress_callback:
            try:
                self.progress_callback(step, percent, message)
            except Exception:
                pass

    def process_single_video(self, url: str, force_asr: bool = False) -> ProcessResult:
        """
        处理单个视频的完整管线
        """
        import time
        start_time = time.time()

        self.reset()
        result = ProcessResult(video_url=url)

        # Step 1: 提取视频信息
        if self._is_cancelled():
            result.cancelled = True
            return result

        self._report_progress("提取视频信息", 5)
        try:
            video_info = extract_video_info(url)
            result.video_title = video_info.title
            result.bvid = video_info.bvid
        except Exception as e:
            result.error = f"视频信息提取失败: {e}"
            return result

        self._report_progress("视频信息获取完成", 10,
                              f"标题: {video_info.title}, 时长: {video_info.duration_str}")

        # Step 2: 获取字幕
        transcript = ""
        source = ""

        if self._is_cancelled():
            result.cancelled = True
            return result

        if not force_asr and video_info.has_ai_subtitles:
            self._report_progress("下载字幕中", 15)
            vtt_path = self.subtitle_extractor.try_extract_subtitles(
                url, video_info.subtitles
            )
            if vtt_path:
                self._report_progress("解析字幕文本", 30)
                transcript = self._parse_subtitle_file(vtt_path)
                source = "字幕提取"
                self._report_progress("字幕提取完成", 40, f"共 {len(transcript)} 字符")
            else:
                force_asr = True

        # Step 3: 语音识别兜底
        if force_asr or not video_info.has_ai_subtitles:
            if self._is_cancelled():
                result.cancelled = True
                return result

            self._report_progress("下载音频中", 20)
            try:
                transcript = self._transcribe_via_asr(url)
                source = "语音识别"
                self._report_progress("语音识别完成", 60, f"共 {len(transcript)} 字符")
            except ASRCancelledError:
                result.cancelled = True
                result.transcript = transcript  # 保留已完成的部分
                return result
            except Exception as e:
                result.error = f"语音识别失败: {e}"
                return result

        if not transcript.strip():
            result.error = "未能获取任何文字内容"
            return result

        result.transcript = transcript
        result.source = source

        # Step 4: AI概述
        if self._is_cancelled():
            result.cancelled = True
            return result

        self._report_progress("生成AI概述中", 65)
        try:
            summary = self._summarize(transcript, video_info.title)
            result.summary = summary
            self._report_progress("AI概述生成完成", 85, f"共 {len(summary)} 字符")
        except Exception as e:
            result.error = f"AI概述生成失败: {e}"
            logger.warning("AI概述失败，但仍会保存逐字稿")

        # Step 5: 写入文件
        if self._is_cancelled():
            result.cancelled = True
            return result

        self._report_progress("写入输出文件", 90)
        try:
            paths = self.output_writer.write_all(
                video_title=video_info.title,
                transcript=transcript,
                summary=result.summary or "(AI概述生成失败)",
                video_url=url,
                duration=video_info.duration_str,
                source=source,
                uploader=video_info.uploader,
                fmt=self.config.output_format or "md",
            )
            result.output_dir = paths.output_dir
            result.transcript_file = paths.transcript_file
            result.summary_file = paths.summary_file
        except Exception as e:
            result.error = f"文件写入失败: {e}"
            return result

        result.duration_seconds = time.time() - start_time
        self._report_progress("处理完成", 100, f"耗时 {result.duration_seconds:.1f} 秒")
        return result

    def _parse_subtitle_file(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if suffix == ".vtt":
            return parse_vtt_to_text(content)
        elif suffix == ".srt":
            return parse_srt_to_text(content)
        else:
            return parse_vtt_to_text(content)

    def _transcribe_via_asr(self, url: str) -> str:
        asr = ASREngine(self.config)
        if not asr.is_available():
            raise RuntimeError("faster-whisper 未安装，请运行: pip install faster-whisper")
        if not asr.is_model_downloaded():
            raise RuntimeError(
                "语音识别模型尚未下载。\n请前往「设置」页面点击「下载模型」按钮。"
            )

        model = self.config.whisper_model
        from src.pipeline.asr_engine import ACCURACY_PRESETS
        preset_name = ""
        for name, info in ACCURACY_PRESETS.items():
            if info["model"] == model:
                preset_name = f" ({name})"
                break

        step_label = f"语音识别 · {model}{preset_name}"
        self._report_progress(step_label, 20, f"模型加载中 ({model})...")

        def asr_progress(pct: int, msg: str):
            overall = 20 + int(pct * 0.65)
            self._report_progress(step_label, overall, msg)

        return asr.transcribe_from_url(
            url=url,
            language="zh",
            cancel_event=self._cancel_event,
            progress_callback=asr_progress,
        )

    def _summarize(self, transcript: str, video_title: str) -> str:
        summarizer = AISummarizer(self.config)
        detail = self.config.summary_detail or "大致概览"
        model = self.config.api_model or "deepseek-chat"

        def progress_wrapper(message: str):
            self._report_progress(f"AI概述 · {detail} · {model}", 70, message)

        return summarizer.summarize(
            transcript=transcript,
            video_title=video_title,
            detail=detail,
            progress_callback=progress_wrapper,
        )
