"""
管线编排器
"""
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

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
    video_title: str = ""
    video_url: str = ""
    bvid: str = ""
    transcript: str = ""
    summary: str = ""
    output_dir: Optional[Path] = None
    transcript_file: Optional[Path] = None
    summary_file: Optional[Path] = None
    source: str = ""
    error: Optional[str] = None
    cancelled: bool = False
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return self.error is None


class PipelineManager:
    def __init__(self, config: Config, progress_callback: Optional[Callable] = None):
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
        self._cancel_event.set()

    def reset(self):
        self._cancel_event.clear()

    def _is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _gui(self, pct: int, msg: str = ""):
        """更新进度条，不写控制台"""
        if self.progress_callback:
            try:
                self.progress_callback("", pct, msg)
            except Exception:
                pass

    def _log(self, msg: str):
        """控制台一行"""
        logger.info(msg)

    def process_single_video(self, url: str, force_asr: bool = False) -> ProcessResult:
        import time
        start = time.time()
        self.reset()
        result = ProcessResult(video_url=url)

        # Step 1: 视频信息
        if self._is_cancelled():
            result.cancelled = True
            return result
        try:
            vi = extract_video_info(url)
            result.video_title = vi.title
            result.bvid = vi.bvid
        except Exception as e:
            result.error = f"视频信息提取失败: {e}"
            return result

        # Step 2: 字幕 或 ASR
        transcript = ""
        source = ""

        if self._is_cancelled():
            result.cancelled = True
            return result

        if not force_asr and vi.has_ai_subtitles:
            vtt = self.subtitle_extractor.try_extract_subtitles(url, vi.subtitles)
            if vtt:
                transcript = self._parse_subtitle_file(vtt)
                source = "字幕提取"
                self._log("字幕提取完成")
            else:
                force_asr = True

        if force_asr or not vi.has_ai_subtitles:
            if self._is_cancelled():
                result.cancelled = True
                return result
            model = self.config.whisper_model
            self._log(f"加载 {model} → 下载音频完成")
            try:
                transcript = self._transcribe_via_asr(url)
                source = "语音识别"
                self._gui(100)
            except ASRCancelledError:
                result.cancelled = True
                result.transcript = transcript
                return result
            except Exception as e:
                result.error = f"语音识别失败: {e}"
                return result

        if not transcript.strip():
            result.error = "未能获取任何文字内容"
            return result

        result.transcript = transcript
        result.source = source

        # 输出目录
        if self._is_cancelled():
            result.cancelled = True
            return result
        try:
            paths = self.output_writer.write_all(
                video_title=vi.title, transcript=transcript,
                summary="", video_url=url, duration=vi.duration_str,
                source=source, uploader=vi.uploader,
                fmt=self.config.output_format or "md",
            )
            result.output_dir = paths.output_dir
            result.transcript_file = paths.transcript_file
            result.summary_file = paths.summary_file
        except Exception as e:
            result.error = f"文件写入失败: {e}"
            return result

        self._log(f"输出: {result.output_dir}")

        # Step 3: AI概述
        if self._is_cancelled():
            result.cancelled = True
            return result
        summary = ""
        detail = self.config.summary_detail or "精细概览"
        model = self.config.api_model or "?"
        self._log("AI概述生成中...")
        try:
            summary = self._summarize(transcript, vi.title)
            result.summary = summary
            # 写 summary
            self.output_writer.write_summary(
                video_title=vi.title, summary=summary, video_url=url,
                duration=vi.duration_str, model_name=model, uploader=vi.uploader,
                fmt=self.config.output_format or "md",
            )
        except Exception as e:
            result.error = f"AI概述生成失败: {e}"

        result.duration_seconds = time.time() - start
        t = int(result.duration_seconds)
        ts = f"{t//60}分{t%60}秒" if t >= 60 else f"{t}秒"
        self._log(f"完成: {len(transcript)} 字符 | 总耗时 {ts}")
        self._gui(100)
        return result

    def _parse_subtitle_file(self, fp: Path) -> str:
        s = fp.suffix.lower()
        c = fp.read_text("utf-8")
        return parse_vtt_to_text(c) if s == ".vtt" else parse_srt_to_text(c) if s == ".srt" else parse_vtt_to_text(c)

    def _transcribe_via_asr(self, url: str) -> str:
        asr = ASREngine(self.config)
        if not asr.is_available():
            raise RuntimeError("faster-whisper 未安装")
        if not asr.is_model_downloaded():
            raise RuntimeError("语音识别模型未下载，请到设置页下载")
        # ASR 进度映射 0-100，只反映音频处理进度
        return asr.transcribe_from_url(
            url=url, language="zh", cancel_event=self._cancel_event,
            progress_callback=lambda p, m: self._gui(p, m),
        )

    def _summarize(self, transcript: str, video_title: str) -> str:
        s = AISummarizer(self.config)
        self._gui(100, "正在生成概览，半分钟左右...")
        result = s.summarize(
            transcript=transcript, video_title=video_title,
            detail=self.config.summary_detail or "精细概览",
        )
        self._gui(100)
        return result
