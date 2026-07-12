"""
单视频处理 Tab
"""
import queue
import threading
import customtkinter as ctk
from pathlib import Path

from src.config import Config
from src.gui.widgets import URLInput, ProgressBar, LogPanel, InfoCard
from src.pipeline.orchestrator import PipelineManager, ProcessResult
from src.utils.validators import validate_bilibili_url


class SingleVideoTab(ctk.CTkFrame):
    """单视频处理页面"""

    def __init__(self, master, config: Config, log_queue: queue.Queue, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.log_queue = log_queue
        self._processing = False
        self._pipeline = None

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        # 顶部说明
        header = ctk.CTkLabel(
            self,
            text="单视频处理",
            font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold"),
        )
        header.pack(anchor="w", padx=10, pady=(10, 5))

        desc = ctk.CTkLabel(
            self,
            text="输入B站视频链接，自动提取字幕/音频并生成完整文字版和AI概述",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color="#8b949e",
        )
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # URL输入区域
        url_card = ctk.CTkFrame(self)
        url_card.pack(fill="x", padx=10, pady=(0, 10))

        url_label = ctk.CTkLabel(
            url_card,
            text="视频链接",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
        )
        url_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.url_input = URLInput(url_card, on_process=self._on_process_clicked)
        self.url_input.pack(fill="x", padx=10, pady=(0, 10))

        # 视频信息卡片
        self.info_card = InfoCard(self)
        self.info_card.pack(fill="x", padx=10, pady=(0, 10))

        # 进度条
        self.progress = ProgressBar(self)
        self.progress.pack(fill="x", padx=10, pady=(0, 10))

        # 日志面板
        log_label = ctk.CTkLabel(
            self,
            text="输出日志",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
        )
        log_label.pack(anchor="w", padx=10, pady=(5, 5))

        self.log_panel = LogPanel(self)
        self.log_panel.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 底部按钮
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.open_folder_btn = ctk.CTkButton(
            bottom_frame,
            text="打开输出文件夹",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30,
            width=120,
            state="disabled",
            command=self._open_output_folder,
        )
        self.open_folder_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(
            bottom_frame,
            text="停止",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30,
            width=80,
            fg_color="#f44336",
            hover_color="#c62828",
            command=self._on_stop_clicked,
        )
        # 停止按钮初始隐藏
        # self.stop_btn.pack(side="left", padx=(0, 8))

        self.retry_btn = ctk.CTkButton(
            bottom_frame,
            text="重试",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30,
            width=80,
            fg_color="transparent",
            border_width=1,
            state="disabled",
            command=self._on_process_clicked,
        )
        self.retry_btn.pack(side="left")

        # 存储上次处理结果
        self._last_result = None

    def _on_process_clicked(self):
        """点击处理按钮"""
        if self._processing:
            return

        url = self.url_input.get_url()

        # URL验证
        if not url:
            self.log_panel.warning("请输入B站视频链接")
            return

        if not validate_bilibili_url(url):
            self.log_panel.error("无效的B站视频链接，请检查后重试")
            return

        # 检查配置
        if not self.config.is_api_configured:
            self.log_panel.warning("未配置 DeepSeek API Key，将只能生成逐字稿（不含AI概述）")

        # 开始处理
        self._processing = True
        self.url_input.set_processing(True)
        self.retry_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.progress.update(0, "开始处理...")
        self.info_card.clear()
        self._last_result = None

        # 显示停止按钮
        self.stop_btn.pack(side="left", padx=(0, 8), before=self.retry_btn)

        # 在后台线程执行
        thread = threading.Thread(target=self._process_video, args=(url,), daemon=True)
        thread.start()

    def _on_stop_clicked(self):
        """停止处理"""
        self.log_panel.warning("正在停止...")
        if self._pipeline:
            self._pipeline.cancel()
        self.stop_btn.configure(state="disabled", text="停止中...")

    def _process_video(self, url: str):
        """后台处理视频"""
        self._pipeline = PipelineManager(
            config=self.config,
            progress_callback=self._on_progress,
        )

        result = self._pipeline.process_single_video(url)

        # 回到主线程更新UI
        self.after(0, lambda: self._on_process_finished(result))

    def _on_progress(self, step: str, percent: int, message: str = ""):
        """进度回调（在后台线程中调用）"""
        self.after(0, lambda: self._update_progress_ui(step, percent, message))

    def _update_progress_ui(self, step: str, percent: int, message: str = ""):
        """更新进度UI"""
        self.progress.update(percent, step)
        if message:
            self.log_panel.info(message)

    def _on_process_finished(self, result: ProcessResult):
        """处理完成"""
        self._processing = False
        self._pipeline = None
        self.url_input.set_processing(False)
        self.retry_btn.configure(state="normal")

        # 隐藏停止按钮
        self.stop_btn.pack_forget()
        self.stop_btn.configure(state="normal", text="停止")

        if result.cancelled:
            self.progress.update(0, "已取消")
            self.log_panel.warning("处理已被用户取消")
            self.info_card.set_info("已取消", "可在下方日志查看已生成的部分内容")
            # 如果有部分转录结果，仍然保存
            if result.transcript:
                self.log_panel.info(f"已保存部分文字 ({len(result.transcript)} 字符)")
        elif result.error:
            self.progress.update(0, "处理失败")
            self.log_panel.error(result.error)
            self.info_card.set_info("处理失败", result.error)
        else:
            self.progress.update(100, "完成!")
            self.log_panel.success(f"输出目录: {result.output_dir}")
            self.log_panel.success(f"逐字稿: {result.transcript_file}")
            self.log_panel.success(f"AI概述: {result.summary_file}")
            self.log_panel.info(f"总耗时: {result.duration_seconds:.1f} 秒")

            info = f"来源: {result.source} | BV号: {result.bvid}"
            self.info_card.set_info(result.video_title, info)

            if result.output_dir and result.output_dir.exists():
                self.open_folder_btn.configure(state="normal")
                self._last_result = result

    def _open_output_folder(self):
        """打开输出文件夹"""
        import os
        import subprocess

        if self._last_result and self._last_result.output_dir:
            output_dir = str(self._last_result.output_dir)
        else:
            output_dir = str(Path(self.config.output_dir).resolve())

        if os.path.exists(output_dir):
            subprocess.Popen(["explorer", output_dir])
            self.log_panel.info(f"已打开输出文件夹: {output_dir}")
        else:
            self.log_panel.warning("输出文件夹不存在")

    def poll_logs(self):
        """轮询日志队列（由主窗口定时调用）"""
        try:
            while True:
                entry = self.log_queue.get_nowait()
                self.log_panel.add_batch([entry])
        except queue.Empty:
            pass
