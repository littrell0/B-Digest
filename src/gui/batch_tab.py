"""
批量处理 Tab
"""
import queue
import threading
from pathlib import Path

import customtkinter as ctk

from src.config import Config
from src.gui.widgets import LogPanel
from src.pipeline.orchestrator import PipelineManager


TIME_RANGES = [
    ("6小时内", 6),
    ("12小时内", 12),
    ("1天内", 24),
    ("2天内", 48),
    ("4天内", 96),
    ("7天内", 168),
]


class BatchTab(ctk.CTkFrame):
    """批量处理页面"""

    def __init__(self, master, config: Config, log_queue: queue.Queue, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.log_queue = log_queue
        self._client = None
        self._videos = []          # 当前加载的视频列表
        self._check_vars = []      # 复选框变量
        self._video_rows = []      # (row_frame, video_dict)
        self._processing = False
        self._pipeline = None

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        # 头部
        header = ctk.CTkLabel(
            self, text="批量处理",
            font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold"),
        )
        header.pack(anchor="w", padx=10, pady=(10, 3))

        desc = ctk.CTkLabel(
            self, text="登录B站账号，检测关注UP主更新，一键批量处理",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color=None,
        )
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # === 登录区域 ===
        login_card = ctk.CTkFrame(self)
        login_card.pack(fill="x", padx=10, pady=(0, 8))

        login_bar = ctk.CTkFrame(login_card, fg_color="transparent")
        login_bar.pack(fill="x", padx=10, pady=10)

        self.login_status = ctk.CTkLabel(
            login_bar,
            text="登录状态: ○ 未登录",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
        )
        self.login_status.pack(side="left", padx=(0, 10))

        self.login_btn = ctk.CTkButton(
            login_bar,
            text="登录B站",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30, width=90,
            command=self._do_login,
        )
        self.login_btn.pack(side="left")

        self.logout_btn = ctk.CTkButton(
            login_bar,
            text="注销",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30, width=60,
            fg_color="transparent", border_width=1,
            command=self._do_logout,
        )
        # 初始隐藏

        # === 时间范围 + 刷新 ===
        ctrl_card = ctk.CTkFrame(self)
        ctrl_card.pack(fill="x", padx=10, pady=(0, 8))

        ctrl_bar = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        ctrl_bar.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            ctrl_bar, text="时间范围",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
        ).pack(side="left", padx=(0, 8))

        self.range_var = ctk.StringVar(value="12小时内")
        self.range_menu = ctk.CTkOptionMenu(
            ctrl_bar,
            values=[r[0] for r in TIME_RANGES],
            variable=self.range_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        )
        self.range_menu.pack(side="left", padx=(0, 8))

        # 时间预估提示
        time_hint = ctk.CTkLabel(
            ctrl_bar,
            text="扫描: 每个UP主约15秒 | 处理: 视模型和视频长度而定",
            font=ctk.CTkFont(family="Microsoft YaHei", size=9),
            text_color="#6b7280",
        )
        time_hint.pack(side="left", padx=(5, 0))

        self.refresh_btn = ctk.CTkButton(
            ctrl_bar,
            text="刷新视频列表",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30, width=110,
            command=self._do_refresh,
            state="disabled",
        )
        self.refresh_btn.pack(side="left")

        self.filter_btn = ctk.CTkButton(
            ctrl_bar,
            text="UP主筛选",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30, width=80,
            fg_color="transparent", border_width=1,
            command=self._open_filter_dialog,
            state="disabled",
        )
        self.filter_btn.pack(side="left", padx=(8, 0))

        # 搜索过滤
        self.search_entry = ctk.CTkEntry(
            ctrl_bar,
            placeholder_text="搜索UP主或视频...",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=150,
        )
        self.search_entry.pack(side="left", padx=(8, 0))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_video_list())

        self.video_count = ctk.CTkLabel(
            ctrl_bar,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color=None,
        )
        self.video_count.pack(side="left", padx=15)

        # === 视频列表（固定高度，约5行） ===
        video_outer = ctk.CTkFrame(self, height=170)
        video_outer.pack(fill="x", padx=10, pady=(0, 5))
        video_outer.pack_propagate(False)

        self.video_frame = ctk.CTkScrollableFrame(
            video_outer,
            label_text="关注UP主新视频",
            label_font=ctk.CTkFont(family="Microsoft YaHei", size=12),
        )
        self.video_frame.pack(fill="both", expand=True)

        # 空状态
        self.empty_label = ctk.CTkLabel(
            self.video_frame,
            text="请先登录并刷新视频列表",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            text_color=None,
        )
        self.empty_label.pack(pady=30)

        # === 操作按钮 ===
        action_card = ctk.CTkFrame(self)
        action_card.pack(fill="x", padx=10, pady=(0, 5))

        action_bar = ctk.CTkFrame(action_card, fg_color="transparent")
        action_bar.pack(fill="x", padx=10, pady=8)

        self.select_all_btn = ctk.CTkButton(
            action_bar, text="全选", width=60, height=28,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="transparent", border_width=1,
            command=lambda: self._toggle_all(True),
        )
        self.select_all_btn.pack(side="left", padx=(0, 5))

        self.deselect_btn = ctk.CTkButton(
            action_bar, text="取消全选", width=70, height=28,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="transparent", border_width=1,
            command=lambda: self._toggle_all(False),
        )
        self.deselect_btn.pack(side="left", padx=(0, 15))

        self.batch_btn = ctk.CTkButton(
            action_bar, text="批量处理选中 (0个)", height=32,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            command=self._do_batch_process,
        )
        self.batch_btn.pack(side="left", padx=(0, 8))

        self.batch_stop_btn = ctk.CTkButton(
            action_bar, text="停止", width=60, height=32,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="#f44336", hover_color="#c62828",
            command=self._do_stop,
        )
        # 初始隐藏

        # 批量进度
        self.batch_progress = ctk.CTkProgressBar(action_card, height=20)
        self.batch_progress.pack(fill="x", padx=10, pady=(0, 2))
        self.batch_progress.set(0)
        self._bc = self.batch_progress.winfo_children()[0]
        self._bt = self._bc.create_text(100, 10, text="", font=("Microsoft YaHei", 10),
                                         fill="#e0e0e0" if ctk.get_appearance_mode() == "Dark" else "#4a3340")
        self._bc.bind("<Configure>", lambda e: self._bc.coords(self._bt, e.width//2, e.height//2))

        self.sub_progress = ctk.CTkProgressBar(action_card, progress_color="#6c63ff", height=20)
        self.sub_progress.pack(fill="x", padx=10, pady=(0, 2))
        self.sub_progress.set(0)

        # Canvas 文字（零背景）
        tc = "#c4b5fd" if ctk.get_appearance_mode() == "Dark" else "#d06078"
        self._sub_canvas = self.sub_progress.winfo_children()[0]
        self._sub_text = self._sub_canvas.create_text(100, 9, text="", font=("Microsoft YaHei", 10), fill=tc)
        self._sub_canvas.bind("<Configure>", lambda e: self._sub_canvas.coords(self._sub_text, e.width//2, e.height//2))

        # === 日志（撑满剩余空间，最少6行） ===
        log_outer = ctk.CTkFrame(self)
        log_outer.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.log_panel = LogPanel(log_outer)
        self.log_panel.pack(fill="both", expand=True)

    # ===== 登录 =====
    def _do_login(self):
        """尝试登录"""
        sessdata = self.config.bili_sessdata
        bili_jct = self.config.bili_bili_jct
        buvid3 = self.config.bili_buvid3

        if not sessdata or not bili_jct:
            self.log_panel.warning("请在「设置」页填写 B站 Cookie（SESSDATA+bili_jct）并保存")
            return

        self.login_btn.configure(state="disabled", text="登录中...")
        self.log_panel.info("正在验证B站登录...")

        def do():
            from src.bilibili.client import BilibiliClient
            client = BilibiliClient(sessdata, bili_jct, buvid3)
            result = client.test_login()
            self.after(0, lambda: self._on_login_result(client, result))

        threading.Thread(target=do, daemon=True).start()

    def _on_login_result(self, client, result):
        self.login_btn.configure(state="normal", text="登录B站")
        if result["ok"]:
            self._client = client
            self.login_status.configure(
                text=f"● 已登录: {result.get('name', '')}",
                text_color="#3fb950",
            )
            self.login_btn.pack_forget()
            self.logout_btn.pack(side="left")
            self.refresh_btn.configure(state="normal")
            self.filter_btn.configure(state="normal")
            self.log_panel.success(f"登录成功！欢迎，{result.get('name', '')}")
        else:
            self._client = None
            self.login_status.configure(text="○ 登录失败", text_color="#f85149")
            self.log_panel.error(f"登录失败: {result.get('error', '未知错误')}")

    def _do_logout(self):
        self._client = None
        self._videos = []
        self._check_vars = []
        self.login_status.configure(text="○ 未登录", text_color="#e0e0e0")
        self.logout_btn.pack_forget()
        self.login_btn.pack(side="left")
        self.refresh_btn.configure(state="disabled")
        self.filter_btn.configure(state="disabled")
        self._clear_video_list()
        self.log_panel.info("已注销")

    # ===== 刷新视频列表 =====
    def _get_hours(self) -> int:
        choice = self.range_var.get()
        for label, h in TIME_RANGES:
            if choice == label:
                return h
        return 12

    def _do_refresh(self):
        if not self._client:
            self.log_panel.warning("请先登录")
            return

        hours = self._get_hours()
        self.refresh_btn.configure(state="disabled", text="刷新中...")
        self.log_panel.info(f"正在获取 {hours} 小时内关注UP主的新视频...")

        def do():
            try:
                excluded = [
                    uid.strip() for uid in self.config.excluded_uids.split(",")
                    if uid.strip()
                ]
                videos = self._client.get_recent_videos_from_followings(
                    hours=hours,
                    excluded_uids=excluded,
                    progress_callback=lambda cur, total, msg:
                        self.after(0, lambda: self.log_panel.info(msg))
                )
                self.after(0, lambda: self._on_videos_loaded(videos))
            except Exception as e:
                self.after(0, lambda: self._on_refresh_error(str(e)))

        threading.Thread(target=do, daemon=True).start()

    def _on_videos_loaded(self, videos):
        self._videos = videos
        self.refresh_btn.configure(state="normal", text="刷新视频列表")
        self.video_count.configure(text=f"共 {len(videos)} 个视频")

        self._clear_video_list()
        self._check_vars = []
        self._video_rows = []

        if not videos:
            self.empty_label = ctk.CTkLabel(
                self.video_frame,
                text="该时间段内没有新视频",
                font=ctk.CTkFont(family="Microsoft YaHei", size=12),
                text_color=None,
            )
            self.empty_label.pack(pady=30)
            self._update_batch_btn()
            return

        from src.utils.validators import sanitize_filename

        for v in videos:
            # 检查是否已处理
            output_dir = Path(self.config.output_dir)
            safe_author = sanitize_filename(v["author"])
            safe_title = sanitize_filename(v["title"])
            already_done = (output_dir / safe_author / safe_title / "transcript.md").exists()
            # 也检查旧格式（无UP主目录）
            if not already_done:
                already_done = (output_dir / safe_title / "transcript.md").exists()

            var = ctk.BooleanVar(value=not already_done)  # 已处理默认不勾
            self._check_vars.append(var)

            row = ctk.CTkFrame(self.video_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            self._video_rows.append((row, v))

            cb = ctk.CTkCheckBox(
                row, text="", variable=var, width=20,
                checkbox_width=18, checkbox_height=20,
                command=self._update_batch_btn,
            )
            cb.pack(side="left", padx=(0, 5))

            label = f"{v['author']} · {v['title'][:60]} ({v['pubdate_str']})"
            if already_done:
                label += "  ✓已处理"
            ctk.CTkLabel(
                row, text=label,
                font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                anchor="w",
                text_color="#3fb950" if already_done else None,
            ).pack(side="left")

        self._update_batch_btn()
        self.log_panel.success(f"找到 {len(videos)} 个视频")

    def _on_refresh_error(self, error):
        self.refresh_btn.configure(state="normal", text="刷新视频列表")
        self.log_panel.error(f"获取视频失败: {error}")

    def _clear_video_list(self):
        for w in self.video_frame.winfo_children():
            w.destroy()

    def _filter_video_list(self):
        """根据搜索框过滤视频列表"""
        query = self.search_entry.get().strip().lower()
        for row, v in self._video_rows:
            if not query or query in v["author"].lower() or query in v["title"].lower():
                row.pack(fill="x", pady=2)
            else:
                row.pack_forget()

    def _toggle_all(self, checked: bool):
        for var in self._check_vars:
            var.set(checked)
        self._update_batch_btn()

    def _update_batch_btn(self):
        count = sum(1 for v in self._check_vars if v.get())
        self.batch_btn.configure(text=f"批量处理选中 ({count}个)")

    # ===== 批量处理 =====
    def _do_batch_process(self):
        if self._processing:
            return

        selected = [v for i, v in enumerate(self._videos) if self._check_vars[i].get()]
        if not selected:
            self.log_panel.warning("请勾选要处理的视频")
            return

        self._processing = True
        self.batch_btn.configure(state="disabled")
        self.batch_stop_btn.pack(side="left", padx=(0, 8))
        self.batch_progress.set(0)
        self._bc.itemconfigure(self._bt, text=f"准备处理 {len(selected)} 个...")

        if not self.config.is_api_configured:
            self.log_panel.warning("未配置 DeepSeek API Key，将只生成逐字稿")

        def do():
            self._pipeline = PipelineManager(
                config=self.config,
                progress_callback=lambda step, pct, msg:
                    self.after(0, lambda: self._update_sub_progress(pct, msg)),
            )

            for i, v in enumerate(selected):
                if self._pipeline._cancel_event.is_set():
                    break

                idx = i + 1
                total = len(selected)
                self.after(0, lambda i=idx, t=total: self._update_batch_ui(
                    i, t, f"处理 {i}/{t}: {v['author']} · {v['title'][:40]}"
                ))

                url = f"https://www.bilibili.com/video/{v['bvid']}"
                result = self._pipeline.process_single_video(url)

                if result.error:
                    self.after(0, lambda r=result, vi=v, n=idx: self._log_result(r, vi, n))
                elif result.cancelled:
                    self.after(0, lambda: self.log_panel.warning("批量处理已停止"))
                    break
                else:
                    self.after(0, lambda r=result, vi=v, n=idx: self._log_result(r, vi, n))

            self.after(0, self._on_batch_finished)

        threading.Thread(target=do, daemon=True).start()

    def _update_sub_progress(self, pct: int, msg: str):
        """更新当前视频的子进度"""
        self.sub_progress.set(pct / 100.0)
        text = msg if msg else f"{pct}%"
        self._sub_canvas.itemconfigure(self._sub_text, text=text)

    def _update_batch_ui(self, current, total, msg):
        self.batch_progress.set(current / total)
        self._bc.itemconfigure(self._bt, text=f"{current}/{total} · {msg}")

    def _log_result(self, result, video, idx):
        if result.error:
            self.log_panel.error(f"[{idx}] {video['author']} · {video['title'][:30]}: {result.error}")
        else:
            self.log_panel.success(f"[{idx}] {video['author']} · {video['title'][:30]}: 完成 ({result.duration_seconds:.0f}s)")

    def _on_batch_finished(self):
        self._processing = False
        self._pipeline = None
        self.batch_btn.configure(state="normal")
        self.batch_stop_btn.pack_forget()
        self._bc.itemconfigure(self._bt, text="批量处理完成")
        self.log_panel.success("全部处理完成！")

    def _do_stop(self):
        self.log_panel.warning("正在停止...")
        if self._pipeline:
            self._pipeline.cancel()
        self.batch_stop_btn.configure(state="disabled", text="停止中...")

    # ===== UP主筛选 =====
    def _open_filter_dialog(self):
        """打开UP主筛选弹窗"""
        if not self._client:
            return

        self.filter_btn.configure(state="disabled", text="加载中...")

        def do():
            try:
                followings = self._client.get_followings()
                self.after(0, lambda: self._show_filter_dialog(followings))
            except Exception as e:
                self.after(0, lambda: self.log_panel.error(f"获取关注列表失败: {e}"))
                self.after(0, lambda: self.filter_btn.configure(state="normal", text="UP主筛选"))

        threading.Thread(target=do, daemon=True).start()

    def _show_filter_dialog(self, followings: list):
        """显示筛选弹窗"""
        self.filter_btn.configure(state="normal", text="UP主筛选")

        excluded = set(
            uid.strip() for uid in self.config.excluded_uids.split(",") if uid.strip()
        )

        dialog = ctk.CTkToplevel(self)
        dialog.title("UP主筛选 — 取消勾选不需要的UP主")
        dialog.geometry("500x500")
        dialog.transient(self)
        dialog.grab_set()

        # 说明
        ctk.CTkLabel(
            dialog, text="取消勾选的UP主在刷新视频列表时将被跳过",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color=None,
        ).pack(pady=(10, 5))

        # 全选/取消
        btn_bar = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_bar.pack(fill="x", padx=10, pady=5)

        def select_all():
            for var in check_vars:
                var.set(True)

        def deselect_all():
            for var in check_vars:
                var.set(False)

        ctk.CTkButton(btn_bar, text="全选", width=60, height=26,
                      font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                      fg_color="transparent", border_width=1,
                      command=select_all).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_bar, text="取消全选", width=70, height=26,
                      font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                      fg_color="transparent", border_width=1,
                      command=deselect_all).pack(side="left")

        # 列表
        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill="both", expand=True, padx=10, pady=5)

        check_vars = []
        for up in followings:
            var = ctk.BooleanVar(value=up["uid"] not in excluded)
            check_vars.append(var)

            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkCheckBox(row, text="", variable=var,
                            width=20, checkbox_width=16, checkbox_height=16).pack(side="left")
            ctk.CTkLabel(row, text=up["name"],
                         font=ctk.CTkFont(family="Microsoft YaHei", size=11)).pack(side="left", padx=5)

        # 保存按钮
        def save():
            excluded_uids = []
            for i, up in enumerate(followings):
                if not check_vars[i].get():
                    excluded_uids.append(up["uid"])
            self.config.excluded_uids = ",".join(excluded_uids)
            self.config.save()
            count = len(followings) - len(excluded_uids)
            self.log_panel.info(f"已保存筛选: {count}/{len(followings)} 个UP主启用")
            dialog.destroy()
            # 自动刷新视频列表
            self.after(200, self._do_refresh)

        ctk.CTkButton(
            dialog, text="保存筛选", height=32,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            command=save,
        ).pack(pady=(5, 10))

    def poll_logs(self):
        try:
            while True:
                entry = self.log_queue.get_nowait()
                self.log_panel.add_batch([entry])
        except queue.Empty:
            pass
