"""
语音识别引擎 - 基于 faster-whisper 的本地语音转文字
"""
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from src.config import Config
from src.utils.validators import ytdlp_cmd

logger = logging.getLogger("bili_summarizer")


class ASRCancelledError(Exception):
    """语音识别被用户取消"""
    pass


# 识别精确度预设
ACCURACY_PRESETS = {
    "最精确": {
        "model": "large-v3",
        "accuracy_pct": "95%",
        "speed_per_min": "3.0 min",
        "scene": "重要内容归档、专业字幕制作",
        "desc": "最高准确度，速度最慢",
    },
    "精确": {
        "model": "medium",
        "accuracy_pct": "88%",
        "speed_per_min": "1.5 min",
        "scene": "日常视频笔记、学习内容整理",
        "desc": "高准确度，中等速度",
    },
    "普通": {
        "model": "small",
        "accuracy_pct": "75%",
        "speed_per_min": "0.5 min",
        "scene": "快速浏览、大量视频筛选",
        "desc": "一般准确度，速度较快",
    },
    "急速": {
        "model": "tiny",
        "accuracy_pct": "60%",
        "speed_per_min": "0.2 min",
        "scene": "超快速预览、实时转写",
        "desc": "最低准确度，速度最快",
        "note": "（不适合中文视频，不推荐）",
    },
}

# 模型信息 (只保留四个)
MODEL_INFO = {
    "tiny":      {"size": 300_000_000, "repo": "Systran/faster-whisper-tiny",     "accuracy_pct": "60%", "speed_per_min": "0.2 min"},
    "small":     {"size": 1_300_000_000, "repo": "Systran/faster-whisper-small",   "accuracy_pct": "75%", "speed_per_min": "0.5 min"},
    "medium":    {"size": 3_500_000_000, "repo": "Systran/faster-whisper-medium",  "accuracy_pct": "88%", "speed_per_min": "1.5 min"},
    "large-v3":  {"size": 3_000_000_000, "repo": "Systran/faster-whisper-large-v3","accuracy_pct": "95%", "speed_per_min": "3.0 min"},
}


def _get_dir_size(dir_path: Path) -> int:
    if not dir_path.exists():
        return 0
    total = 0
    for f in dir_path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


class ASREngine:
    AVAILABLE_MODELS = list(MODEL_INFO.keys())

    def __init__(self, config: Config):
        self.config = config
        self._model = None
        self._loaded_model_size = None

        if config.hf_endpoint:
            os.environ.setdefault("HF_ENDPOINT", config.hf_endpoint)

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_local_model_path(self, model_size: Optional[str] = None) -> Optional[Path]:
        if model_size is None:
            model_size = self.config.whisper_model
        if model_size not in self.AVAILABLE_MODELS:
            model_size = "large-v3"
        model_dir = Path(self.config.model_dir)
        if not model_dir.is_absolute():
            # 打包后 exe 同级目录，开发时项目根目录
            if getattr(sys, 'frozen', False):
                model_dir = Path(sys.executable).parent / model_dir
            else:
                model_dir = Path(__file__).parent.parent.parent / model_dir
        return model_dir / f"faster-whisper-{model_size}"

    def is_model_downloaded(self, model_size: Optional[str] = None) -> bool:
        if model_size is None:
            model_size = self.config.whisper_model
        if model_size not in self.AVAILABLE_MODELS:
            model_size = "large-v3"
        local_path = self._get_local_model_path(model_size)
        if not local_path.exists():
            return False
        required = ["config.json", "tokenizer.json", "model.bin"]
        for fname in required:
            fpath = local_path / fname
            if not fpath.exists():
                if fname == "model.bin":
                    alts = list(local_path.glob("model.*"))
                    if not any(a.suffix in (".bin", ".safetensors", ".pt", ".onnx") and a.stat().st_size > 500_000_000 for a in alts):
                        return False
                else:
                    return False
        return True

    def get_model_downloaded_size(self, model_size: Optional[str] = None) -> int:
        if model_size is None:
            model_size = self.config.whisper_model
        if model_size not in self.AVAILABLE_MODELS:
            return 0
        return _get_dir_size(self._get_local_model_path(model_size))

    def get_model_expected_size(self, model_size: Optional[str] = None) -> int:
        if model_size is None:
            model_size = self.config.whisper_model
        if model_size not in self.AVAILABLE_MODELS:
            model_size = "large-v3"
        return MODEL_INFO[model_size]["size"]

    @classmethod
    def get_model_scores(cls, model_size: str) -> dict:
        """获取模型的评分信息"""
        info = MODEL_INFO.get(model_size, MODEL_INFO["large-v3"])
        return {
            "accuracy_pct": info.get("accuracy_pct", "N/A"),
            "speed_per_min": info.get("speed_per_min", "N/A"),
        }

    @classmethod
    def get_preset(cls, preset_name: str) -> Optional[dict]:
        """根据预设名称获取模型"""
        return ACCURACY_PRESETS.get(preset_name)

    def download_model(
        self,
        model_size: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> None:
        """下载模型到本地"""
        if model_size is None:
            model_size = self.config.whisper_model
        if model_size not in self.AVAILABLE_MODELS:
            raise ValueError(f"不支持的模型: {model_size}")

        info = MODEL_INFO[model_size]
        expected_mb = info["size"] / 1_000_000
        local_dir = self._get_local_model_path(model_size)
        local_dir.mkdir(parents=True, exist_ok=True)

        if self.config.hf_endpoint:
            os.environ.setdefault("HF_ENDPOINT", self.config.hf_endpoint)

        started_size = _get_dir_size(local_dir)
        download_done = threading.Event()

        def poll_progress():
            last_size = started_size
            stall_count = 0
            while not download_done.is_set():
                time.sleep(0.5)
                current = _get_dir_size(local_dir)
                if current > last_size:
                    stall_count = 0
                    last_size = current
                    pct = min(99, int(current / info["size"] * 100))
                    mb = current / 1_000_000
                    elapsed = max(1, time.time() - start_time)
                    speed_mb = (current - started_size) / 1_000_000 / elapsed
                    msg = f"已下载 {mb:.0f}/{expected_mb:.0f}MB ({pct}%) · {speed_mb:.1f}MB/s"
                else:
                    stall_count += 1
                    if stall_count < 10 and started_size == 0:
                        msg = f"正在连接... (共 {expected_mb:.0f}MB)"
                        pct = 0
                    elif stall_count > 120:
                        msg = "下载卡住了，仍在尝试..."
                        pct = 0
                    else:
                        continue
                if progress_callback:
                    progress_callback(pct, msg)

        start_time = time.time()
        if progress_callback:
            progress_callback(0, f"开始下载 {model_size} ({expected_mb:.0f}MB)...")

        poll_thread = threading.Thread(target=poll_progress, daemon=True)
        poll_thread.start()

        try:
            from modelscope import snapshot_download
            ms_repo = f"keepitsimple/faster-whisper-{model_size}"
            snapshot_download(ms_repo, local_dir=str(local_dir))
        except ImportError:
            raise RuntimeError("modelscope 未安装: pip install modelscope")
        except Exception as e:
            raise RuntimeError(f"下载失败: {e}")
        finally:
            download_done.set()
            if progress_callback:
                final = _get_dir_size(local_dir)
                progress_callback(100, f"下载完成 {final/1_000_000:.0f}MB")

    def transcribe(
        self,
        audio_path: Path,
        language: str = "zh",
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> str:
        """音频转文字，支持取消"""
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        if not self.is_available():
            raise RuntimeError("faster-whisper 未安装")

        model_size = self.config.whisper_model
        if model_size not in self.AVAILABLE_MODELS:
            model_size = "large-v3"
        device = self.config.whisper_device
        compute_type = self.config.whisper_compute_type

        # 加载模型
        if self._model is None or self._loaded_model_size != model_size:
            if progress_callback:
                progress_callback(0, f"正在加载模型 {model_size}...")
            from faster_whisper import WhisperModel
            local_path = self._get_local_model_path(model_size)
            model_path = str(local_path) if local_path.exists() else model_size
            logger.info("加载模型: %s (device=%s)", model_path, device)
            self._model = WhisperModel(model_path, device=device, compute_type=compute_type)
            self._loaded_model_size = model_size

        if progress_callback:
            progress_callback(5, "正在进行语音识别...")

        self._transcribe_start = time.time()
        _last_progress_time = 0  # 上次报告进度的时间

        segments, info = self._model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        logger.info("检测语言: %s (置信度: %.2f)", info.language, info.language_probability)

        text_parts = []
        total_segments = 0
        total_duration = info.duration

        for segment in segments:
            # 检查取消
            if cancel_event and cancel_event.is_set():
                logger.info("语音识别已被用户取消 (%d 段已处理)", total_segments)
                partial = "\n".join(text_parts)
                if partial:
                    partial += "\n\n[语音识别已被取消，以上为已完成部分]"
                raise ASRCancelledError(partial or "(未生成任何文本)")

            text = segment.text.strip()
            if text:
                text_parts.append(text)
            total_segments += 1

            # 进度报告: 处理完30秒音频后首次报，之后每30s(真实时间)
            now = time.time()
            elapsed = now - self._transcribe_start
            audio_done = segment.end  # 已处理的音频秒数
            should_report = (
                (_last_progress_time == 0 and audio_done >= 30) or          # 至少30秒音频
                (_last_progress_time == 0 and elapsed >= 60) or             # 或60秒兜底
                (elapsed - _last_progress_time >= 30)                       # 之后每30s
            )

            if progress_callback and should_report:
                _last_progress_time = elapsed
                progress_pct = min(95, 5 + int(90 * (audio_done / total_duration)))
                # 基于实际处理速度估算剩余时间
                speed_ratio = elapsed / max(0.1, audio_done)
                remaining_real_s = max(0, total_duration - audio_done) * speed_ratio
                if remaining_real_s > 3600:
                    eta_str = f"预计剩余 {remaining_real_s/3600:.1f} 小时"
                elif remaining_real_s > 60:
                    eta_str = f"预计剩余 {remaining_real_s/60:.0f} 分钟"
                else:
                    eta_str = f"预计剩余 {remaining_real_s:.0f} 秒"
                progress_callback(progress_pct, f"{progress_pct}% · {eta_str}")

        result = "\n".join(text_parts)
        logger.info("语音识别完成: %d 段, %d 字符, %.1f 分钟", total_segments, len(result), total_duration / 60)

        if progress_callback:
            progress_callback(100, f"识别完成 ({len(result)} 字符)")

        return result

    def download_audio(
        self,
        url: str,
        output_dir: Optional[Path] = None,
        cookie_file: Optional[Path] = None,
        timeout: int = 120,
    ) -> Path:
        """下载音频轨道"""
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="bili_audio_"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = output_dir / "%(title)s.%(ext)s"

        # 多个格式备选，逐步降级
        formats_to_try = [
            ["-f", "bestaudio[ext=m4a]/bestaudio"],
            ["-f", "bestaudio/best"],
            ["-f", "best"],
            [],  # 不指定格式，让 yt-dlp 自己选
        ]

        last_error = None
        for fmt_args in formats_to_try:
            cmd = ytdlp_cmd() + ["--no-playlist", "-o", str(output_template)]
            cmd.extend(fmt_args)
            if cookie_file and cookie_file.exists():
                cmd.extend(["--cookies", str(cookie_file)])
            cmd.append(url)

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"音频下载超时 ({timeout}秒)")

            if result.returncode == 0:
                break  # 成功

            stderr = result.stderr or ""
            last_error = stderr.strip()[-300:]
        else:
            raise RuntimeError(f"音频下载失败（已尝试多种格式）: {last_error or '未知错误'}")

        for ext in ["m4a", "wav", "mp3", "opus", "aac", "webm", "mkv"]:
            files = list(output_dir.glob(f"*.{ext}"))
            if files:
                p = files[0]
                logger.info("音频下载完成: %s (%.1f MB)", p.name, p.stat().st_size / 1_000_000)
                return p

        all_files = list(output_dir.glob("*"))
        for f in all_files:
            if f.is_file() and f.suffix.lower() not in (".vtt", ".srt", ".ass", ".json", ".txt"):
                logger.info("音频下载完成: %s", f.name)
                return f

        raise RuntimeError("音频下载完成但未找到输出文件")

    def transcribe_from_url(
        self,
        url: str,
        language: str = "zh",
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[threading.Event] = None,
        cookie_file: Optional[Path] = None,
        keep_audio: bool = False,
    ) -> str:
        """一站式：下载音频并转写"""
        if progress_callback:
            progress_callback(0, "正在下载音频...")
        audio_path = self.download_audio(url, cookie_file=cookie_file)
        try:
            return self.transcribe(audio_path, language=language,
                                   progress_callback=progress_callback,
                                   cancel_event=cancel_event)
        finally:
            if not keep_audio and audio_path.exists():
                try:
                    audio_path.unlink()
                    import shutil
                    shutil.rmtree(audio_path.parent, ignore_errors=True)
                except Exception:
                    pass
