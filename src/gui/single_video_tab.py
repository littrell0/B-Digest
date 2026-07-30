"""
视频链接 Tab — 支持最多 10 个链接的队列处理
"""
import queue
import threading
from pathlib import Path

import customtkinter as ctk

from src.config import Config
from src.gui.widgets import ProgressBar, LogPanel
from src.pipeline.orchestrator import PipelineManager, ProcessResult
from src.utils.validators import validate_bilibili_url

MAX_VIDEOS = 10


class SingleVideoTab(ctk.CTkFrame):

    def __init__(self, master, config: Config, log_queue: queue.Queue, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.log_queue = log_queue
        self._processing = False
        self._pipeline = None
        self._queue = []  # [{url, title, author}]
        self._last_output = None

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkLabel(
            self, text="视频链接",
            font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold"),
        )
        header.pack(anchor="w", padx=10, pady=(10, 5))

        desc = ctk.CTkLabel(
            self, text=f"粘贴B站视频链接，点击「继续输入」加入队列，最后点「开始处理」。最多 {MAX_VIDEOS} 个",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color=None,
        )
        desc.pack(anchor="w", padx=10, pady=(0, 8))

        # URL 输入区
        url_card = ctk.CTkFrame(self)
        url_card.pack(fill="x", padx=10, pady=(0, 8))

        url_bar = ctk.CTkFrame(url_card, fg_color="transparent")
        url_bar.pack(fill="x", padx=10, pady=10)

        self.url_entry = ctk.CTkEntry(
            url_bar,
            placeholder_text="https://www.bilibili.com/video/BV...",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            height=34,
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.url_entry.bind("<Return>", lambda e: self._add_to_queue())

        self.add_btn = ctk.CTkButton(
            url_bar, text="继续输入", height=34, width=90,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            command=self._add_to_queue,
        )
        self.add_btn.pack(side="left")

        # 队列列表
        queue_outer = ctk.CTkFrame(self, height=150)
        queue_outer.pack(fill="x", padx=10, pady=(0, 8))
        queue_outer.pack_propagate(False)

        self.queue_label = ctk.CTkLabel(
            queue_outer, text="待处理队列（空）",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
        )
        self.queue_label.pack(anchor="w", padx=10, pady=(8, 2))

        self.queue_frame = ctk.CTkScrollableFrame(queue_outer)
        self.queue_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # 进度条
        self.progress = ProgressBar(self)
        self.progress.pack(fill="x", padx=10, pady=(0, 2))

        # 子进度条（当前视频）
        self.sub_progress = ctk.CTkProgressBar(self, progress_color="#6c63ff", height=20)
        self.sub_progress.pack(fill="x", padx=10, pady=(0, 5))
        self.sub_progress.set(0)
        self._sc = self.sub_progress.winfo_children()[0]
        self._st = self._sc.create_text(100, 9, text="", font=("Microsoft YaHei", 10),
                                         fill="#c4b5fd" if ctk.get_appearance_mode() == "Dark" else "#d06078")
        self._sc.bind("<Configure>", lambda e: self._sc.coords(self._st, e.width//2, e.height//2))

        # 操作按钮
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=10, pady=(0, 8))

        self.start_btn = ctk.CTkButton(
            btn_bar, text="开始处理", height=34, width=110,
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
            command=self._start_processing,
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(
            btn_bar, text="停止", width=70, height=34,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            fg_color="#f44336", hover_color="#c62828",
            command=self._on_stop,
        )

        self.open_btn = ctk.CTkButton(
            btn_bar, text="打开输出文件夹", height=34, width=130,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="transparent", border_width=1,
            state="disabled", command=self._open_folder,
        )
        self.open_btn.pack(side="left", padx=(8, 0))

        # 日志
        ctk.CTkLabel(self, text="输出日志",
                     font=ctk.CTkFont(family="Microsoft YaHei", size=12)).pack(anchor="w", padx=10)
        self.log_panel = LogPanel(self)
        self.log_panel.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ===== 队列管理 =====
    def _add_to_queue(self):
        if self._processing:
            return
        url = self.url_entry.get().strip()
        if not url:
            self.log_panel.warning("请输入B站视频链接")
            return
        if not validate_bilibili_url(url):
            self.log_panel.error("无效的B站视频链接")
            return
        if len(self._queue) >= MAX_VIDEOS:
            self.log_panel.warning(f"最多 {MAX_VIDEOS} 个视频")
            return

        # 快速提取标题
        self.add_btn.configure(state="disabled", text="获取中...")

        def do():
            try:
                from src.pipeline.video_info import extract_video_info
                vi = extract_video_info(url, timeout=15)
                self._queue.append({"url": url, "title": vi.title, "author": vi.uploader})
                self.after(0, self._refresh_queue)
                self.after(0, lambda: self.log_panel.info(f"已添加: {vi.title[:40]}"))
            except Exception as e:
                self.after(0, lambda: self.log_panel.error(f"获取失败: {e}"))
            finally:
                self.after(0, lambda: self.add_btn.configure(
                    state="normal", text="继续输入"))

        threading.Thread(target=do, daemon=True).start()

    def _refresh_queue(self):
        for w in self.queue_frame.winfo_children():
            w.destroy()

        n = len(self._queue)
        self.queue_label.configure(text=f"待处理队列 ({n}/{MAX_VIDEOS})")

        if n >= MAX_VIDEOS:
            self.add_btn.configure(state="disabled", text="已满")
        else:
            self.add_btn.configure(state="normal", text="继续输入")

        if n == 0:
            return

        for i, item in enumerate(self._queue):
            row = ctk.CTkFrame(self.queue_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)

            ctk.CTkLabel(
                row, text=f"{i+1}. {item['author']} · {item['title'][:50]}",
                font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                anchor="w",
            ).pack(side="left")

            ctk.CTkButton(
                row, text="✕", width=24, height=24,
                font=ctk.CTkFont(size=10),
                fg_color="transparent", border_width=1,
                command=lambda idx=i: self._remove_from_queue(idx),
            ).pack(side="right")

    def _remove_from_queue(self, idx: int):
        if 0 <= idx < len(self._queue):
            self._queue.pop(idx)
            self._refresh_queue()

    # ===== 批量处理 =====
    def _start_processing(self):
        if self._processing:
            return
        if not self._queue:
            self.log_panel.warning("请先添加视频链接")
            return
        if not self.config.is_api_configured:
            self.log_panel.warning("未配置 API Key，只能生成逐字稿")

        self._processing = True
        self.add_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 8))
        self.open_btn.configure(state="disabled")
        self.progress.update(0, "准备中...")
        total = len(self._queue)

        def do():
            self._pipeline = PipelineManager(
                config=self.config,
                progress_callback=lambda s, p, m: self.after(
                    0, lambda p=p, m=m: self._update_sub(p, m)),
            )
            for i, item in enumerate(self._queue):
                if self._pipeline._cancel_event.is_set():
                    self.after(0, lambda: self.log_panel.warning("已停止"))
                    break
                idx = i + 1
                self.after(0, lambda i=idx, t=total, item=item:
                    self.progress.update(int(i/t*100), f"{i}/{t} · {item['title'][:30]}"))
                result = self._pipeline.process_single_video(item["url"])
                if result.error:
                    self.after(0, lambda r=result, n=idx:
                        self.log_panel.error(f"[{n}] {r.error}"))
                elif not result.cancelled:
                    self.after(0, lambda r=result:
                        self.log_panel.success(f"输出: {r.output_dir}"))
                    self._last_output = result
            self.after(0, self._on_done)

        threading.Thread(target=do, daemon=True).start()

    def _on_stop(self):
        if self._pipeline:
            self._pipeline.cancel()
            self.stop_btn.configure(state="disabled", text="停止中...")

    def _update_sub(self, pct: int, msg: str):
        self.sub_progress.set(pct / 100.0)
        self._sc.itemconfigure(self._st, text=msg if msg else f"{pct}%")

    def _on_done(self):
        self._processing = False
        self._pipeline = None
        self.start_btn.configure(state="normal")
        self.stop_btn.pack_forget()
        self.stop_btn.configure(state="normal", text="停止")
        self.add_btn.configure(state="normal" if len(self._queue) < MAX_VIDEOS else "disabled")
        if self._last_output:
            self.open_btn.configure(state="normal")
        self.progress.update(100, "完成")
        self.log_panel.success("全部处理完成！")

    def _open_folder(self):
        import os, subprocess
        d = str(Path(self.config.output_dir).resolve())
        if os.path.exists(d):
            subprocess.Popen(["explorer", d])

    def poll_logs(self):
        try:
            while True:
                entry = self.log_queue.get_nowait()
                self.log_panel.add_batch([entry])
        except queue.Empty:
            pass
