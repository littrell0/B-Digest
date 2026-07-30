"""
视频搜索 Tab
"""
import queue
import threading
from datetime import datetime, timedelta

import customtkinter as ctk

from src.config import Config
from src.gui.widgets import LogPanel
from src.pipeline.orchestrator import PipelineManager

DURATION_OPTS = [
    ("全部时长", 0),
    ("10分钟以下", 1),
    ("10-30分钟", 2),
    ("30-60分钟", 3),
    ("60分钟以上", 4),
]

DATE_OPTS = [
    ("全部日期", 0),
    ("最近一天", 1),
    ("最近一周", 7),
]


class SearchTab(ctk.CTkFrame):
    """视频搜索页面"""

    def __init__(self, master, config: Config, log_queue: queue.Queue, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.log_queue = log_queue
        self._videos = []
        self._check_vars = []
        self._processing = False
        self._pipeline = None
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkLabel(
            self, text="视频搜索",
            font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold"),
        )
        header.pack(anchor="w", padx=10, pady=(10, 3))

        desc = ctk.CTkLabel(
            self, text="输入关键词搜索B站视频，勾选后批量处理",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color=None,
        )
        desc.pack(anchor="w", padx=10, pady=(0, 3))

        ctk.CTkLabel(
            self, text="建议每次搜索间隔 30 秒，频繁搜索可能被临时限制",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color="#d29922",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # 搜索栏
        search_card = ctk.CTkFrame(self)
        search_card.pack(fill="x", padx=10, pady=(0, 5))

        bar = ctk.CTkFrame(search_card, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=8)

        self.search_entry = ctk.CTkEntry(
            bar, placeholder_text="输入关键词...",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            height=32, width=200,
        )
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda e: self._do_search())

        self.search_btn = ctk.CTkButton(
            bar, text="搜索", height=32, width=70,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            command=self._do_search,
        )
        self.search_btn.pack(side="left", padx=(0, 15))

        # 视频数量
        ctk.CTkLabel(bar, text="视频数量",
                     font=ctk.CTkFont(family="Microsoft YaHei", size=11)).pack(side="left")
        self.count_var = ctk.StringVar(value="20")
        self.count_menu = ctk.CTkOptionMenu(
            bar, values=["5", "10", "20"], variable=self.count_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11), width=70,
        )
        self.count_menu.pack(side="left", padx=(5, 0))

        # 时长筛选
        ctk.CTkLabel(bar, text="  时长",
                     font=ctk.CTkFont(family="Microsoft YaHei", size=11)).pack(side="left", padx=(15, 0))
        self.dur_var = ctk.StringVar(value="全部时长")
        self.dur_menu = ctk.CTkOptionMenu(
            bar, values=[d[0] for d in DURATION_OPTS], variable=self.dur_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11), width=110,
        )
        self.dur_menu.pack(side="left", padx=(5, 0))

        # 日期筛选
        ctk.CTkLabel(bar, text="  日期",
                     font=ctk.CTkFont(family="Microsoft YaHei", size=11)).pack(side="left", padx=(10, 0))
        self.date_var = ctk.StringVar(value="全部日期")
        self.date_menu = ctk.CTkOptionMenu(
            bar, values=[d[0] for d in DATE_OPTS], variable=self.date_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11), width=110,
        )
        self.date_menu.pack(side="left", padx=(5, 0))

        # 视频列表
        self.video_frame = ctk.CTkFrame(self, height=220)
        self.video_frame.pack(fill="x", padx=10, pady=(5, 5))
        self.video_frame.pack_propagate(False)

        self.video_scroll = ctk.CTkScrollableFrame(
            self.video_frame, label_text="搜索结果",
            label_font=ctk.CTkFont(family="Microsoft YaHei", size=12),
        )
        self.video_scroll.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # 空状态
        ctk.CTkLabel(self.video_scroll, text="输入关键词开始搜索",
                     font=ctk.CTkFont(family="Microsoft YaHei", size=12),
                     text_color=None).pack(pady=30)

        # 操作栏
        action_card = ctk.CTkFrame(self)
        action_card.pack(fill="x", padx=10, pady=(0, 5))
        action_bar = ctk.CTkFrame(action_card, fg_color="transparent")
        action_bar.pack(fill="x", padx=10, pady=6)

        self.select_all_btn = ctk.CTkButton(
            action_bar, text="全选", width=50, height=26,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="transparent", border_width=1,
            command=lambda: self._toggle_all(True),
        )
        self.select_all_btn.pack(side="left", padx=(0, 5))
        self.deselect_btn = ctk.CTkButton(
            action_bar, text="取消", width=50, height=26,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="transparent", border_width=1,
            command=lambda: self._toggle_all(False),
        )
        self.deselect_btn.pack(side="left", padx=(0, 15))

        self.batch_btn = ctk.CTkButton(
            action_bar, text="批量处理选中 (0个)", height=30,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            command=self._do_batch,
        )
        self.batch_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(
            action_bar, text="停止", width=50, height=30,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="#f44336", hover_color="#c62828",
            command=self._do_stop,
        )

        # 进度
        self.batch_progress = ctk.CTkProgressBar(action_card, height=20)
        self.batch_progress.pack(fill="x", padx=10, pady=(0, 2))
        self.batch_progress.set(0)
        tc1 = "#e0e0e0" if ctk.get_appearance_mode() == "Dark" else "#4a3340"
        tc2 = "#c4b5fd" if ctk.get_appearance_mode() == "Dark" else "#d06078"
        self._bc = self.batch_progress.winfo_children()[0]
        self._bt = self._bc.create_text(100, 9, text="", font=("Microsoft YaHei", 10), fill=tc1)
        self._bc.bind("<Configure>", lambda e: self._bc.coords(self._bt, e.width//2, e.height//2))

        self.sub_progress = ctk.CTkProgressBar(action_card, progress_color="#6c63ff", height=20)
        self.sub_progress.pack(fill="x", padx=10, pady=(0, 2))
        self.sub_progress.set(0)
        self._sc = self.sub_progress.winfo_children()[0]
        self._st = self._sc.create_text(100, 9, text="", font=("Microsoft YaHei", 10), fill=tc2)
        self._sc.bind("<Configure>", lambda e: self._sc.coords(self._st, e.width//2, e.height//2))

        # 日志
        log_outer = ctk.CTkFrame(self)
        log_outer.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_panel = LogPanel(log_outer)
        self.log_panel.pack(fill="both", expand=True)

    # ===== 搜索 =====
    def _do_search(self):
        if self.search_btn.cget("state") == "disabled":
            return
        keyword = self.search_entry.get().strip()
        if not keyword:
            self.log_panel.warning("请输入关键词")
            return

        count = int(self.count_var.get())
        dur_code = {d[0]: d[1] for d in DURATION_OPTS}[self.dur_var.get()]
        date_days = {d[0]: d[1] for d in DATE_OPTS}[self.date_var.get()]

        self.search_btn.configure(state="disabled", text="搜索中...")
        self.log_panel.info(f"搜索: {keyword} (最多{count}个)...")

        def do():
            from src.bilibili.client import search_videos

            try:
                data = search_videos(keyword, page=1, duration=dur_code)
                items = data.get("result", [])
            except Exception as e:
                self.after(0, lambda: self.log_panel.error(f"搜索失败: {e}"))
                self.after(0, lambda: self.search_btn.configure(
                    state="normal", text="搜索"))
                return

            all_videos = []
            for v in items:
                if v.get("type") != "video":
                    continue
                bvid = v.get("bvid", "")
                if not bvid:
                    continue
                title = v.get("title", "").replace(
                    '<em class="keyword">', ""
                ).replace("</em>", "")
                all_videos.append({
                    "bvid": bvid,
                    "title": title,
                    "author": v.get("author", "?"),
                    "duration": v.get("duration", "?"),
                    "pubdate": v.get("pubdate", 0),
                    "pubdate_str": datetime.fromtimestamp(
                        v.get("pubdate", 0)
                    ).strftime("%m-%d %H:%M"),
                    "play": v.get("play", 0),
                    "is_pay": v.get("is_pay", False) or (
                        v.get("badgepay", False)
                    ),
                })

            # 日期后过滤
            if date_days > 0:
                cutoff = datetime.now() - timedelta(days=date_days)
                all_videos[:] = [
                    v for v in all_videos
                    if datetime.fromtimestamp(v["pubdate"]) >= cutoff
                ]

            all_videos = all_videos[:count]
            self.after(0, lambda v=all_videos: self._show_results(v))

        threading.Thread(target=do, daemon=True).start()

    def _show_results(self, videos):
        self._videos = videos
        self._check_vars = []
        self.search_btn.configure(state="normal", text="搜索")

        for w in self.video_scroll.winfo_children():
            w.destroy()

        if not videos:
            ctk.CTkLabel(self.video_scroll, text="无搜索结果",
                         font=ctk.CTkFont(family="Microsoft YaHei", size=12),
                         text_color=None).pack(pady=30)
            return

        for v in videos:
            var = ctk.BooleanVar(value=not v.get("is_pay"))
            self._check_vars.append(var)
            row = ctk.CTkFrame(self.video_scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)

            cb = ctk.CTkCheckBox(
                row, text="", variable=var, width=20,
                checkbox_width=16, checkbox_height=16,
                command=self._update_batch_btn,
            )
            cb.pack(side="left")

            pay_tag = " ⚠付费" if v.get("is_pay") else ""
            label = f"{v['author']} · {v['title'][:50]} ({v['duration']} · {v['pubdate_str']}){pay_tag}"
            text_color = "#ff9800" if v.get("is_pay") else None
            ctk.CTkLabel(
                row, text=label,
                font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                anchor="w", text_color=text_color,
            ).pack(side="left")

        self._update_batch_btn()
        self.log_panel.success(f"找到 {len(videos)} 个视频")

    def _toggle_all(self, checked: bool):
        for var in self._check_vars:
            var.set(checked)
        self._update_batch_btn()

    def _update_batch_btn(self):
        n = sum(1 for v in self._check_vars if v.get())
        self.batch_btn.configure(text=f"批量处理选中 ({n}个)")

    # ===== 批量处理 =====
    def _do_batch(self):
        if self._processing:
            return
        selected = [
            self._videos[i] for i, var in enumerate(self._check_vars) if var.get()
        ]
        if not selected:
            self.log_panel.warning("请勾选要处理的视频")
            return

        self._processing = True
        self.batch_btn.configure(state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 8))
        self.batch_progress.set(0)
        self._bc.itemconfigure(self._bt, text="准备中...")

        def do():
            self._pipeline = PipelineManager(
                config=self.config,
                progress_callback=lambda s, p, m: self.after(
                    0, lambda: self._update_sub(p, m)),
            )
            total = len(selected)
            for i, v in enumerate(selected):
                if self._pipeline._cancel_event.is_set():
                    break
                idx = i + 1
                self.after(0, lambda i=idx, t=total: self._update_main(
                    i, t, f"{v['author']} · {v['title'][:40]}"))
                url = f"https://www.bilibili.com/video/{v['bvid']}"
                result = self._pipeline.process_single_video(url)
                if result.error:
                    self.after(0, lambda r=result, n=idx: self.log_panel.error(
                        f"[{n}] {r.error}"))
                elif result.cancelled:
                    self.after(0, lambda: self.log_panel.warning("已停止"))
                    break
            self.after(0, self._on_batch_done)

        threading.Thread(target=do, daemon=True).start()

    def _update_main(self, cur: int, total: int, msg: str):
        self.batch_progress.set(cur / total)
        try:
            self._bc.itemconfigure(self._bt, text=f"{cur}/{total} · {msg}")
        except Exception:
            pass

    def _update_sub(self, pct: int, msg: str):
        self.sub_progress.set(pct / 100.0)
        try:
            self._sc.itemconfigure(self._st, text=msg if msg else f"{pct}%")
        except Exception:
            pass

    def _on_batch_done(self):
        self._processing = False
        self._pipeline = None
        self.batch_btn.configure(state="normal")
        self.stop_btn.pack_forget()
        self.batch_progress.set(1.0)
        self._bc.itemconfigure(self._bt, text="完成")
        self.log_panel.success("全部处理完成！")

    def _do_stop(self):
        if self._pipeline:
            self._pipeline.cancel()
            self.stop_btn.configure(state="disabled", text="停止中...")

    def poll_logs(self):
        try:
            while True:
                self.log_queue.get_nowait()
        except queue.Empty:
            pass
