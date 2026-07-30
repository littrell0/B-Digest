"""
AI 问答 Tab — 基于已处理视频的逐字稿进行问答
UP主 → 视频 树形列表，支持多选
"""
import queue
import threading
from pathlib import Path

import customtkinter as ctk

from src.config import Config


def scan_processed_videos(output_dir: str) -> dict:
    """扫描 output/ 目录，返回 {UP主: [video_dict, ...]}"""
    base = Path(output_dir)
    if not base.exists():
        return {}

    data = {}
    for transcript_file in base.rglob("transcript.md"):
        video_dir = transcript_file.parent
        video_title = video_dir.name
        uploader = video_dir.parent.name if video_dir.parent != base else "未归类"
        summary_file = video_dir / "summary.md"

        if uploader not in data:
            data[uploader] = []

        data[uploader].append({
            "title": video_title,
            "uploader": uploader,
            "path": str(video_dir),
            "transcript_path": str(transcript_file),
            "summary_path": str(summary_file) if summary_file.exists() else "",
        })

    # 排序各UP主下的视频
    for uploader in data:
        data[uploader].sort(key=lambda v: v["title"])
    return data


class QATab(ctk.CTkFrame):
    """AI 问答页面"""

    def __init__(self, master, config: Config, log_queue: queue.Queue, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.log_queue = log_queue
        self._engine = None
        self._all_videos = {}         # {uploader: [video_dict]}
        self._check_vars = {}         # {video_path: BooleanVar}

        self._build_ui()
        self._refresh_video_list()

    def _build_ui(self):
        """构建界面"""
        header = ctk.CTkLabel(
            self, text="AI 问答",
            font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold"),
        )
        header.pack(anchor="w", padx=10, pady=(10, 3))

        desc = ctk.CTkLabel(
            self, text="勾选视频，基于逐字稿向 AI 提问视频内容",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color=None,
        )
        desc.pack(anchor="w", padx=10, pady=(0, 8))

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        # === 左侧：视频列表 ===
        left = ctk.CTkFrame(main, width=280)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        # 全选/取消按钮
        btn_bar = ctk.CTkFrame(left, fg_color="transparent")
        btn_bar.pack(fill="x", padx=5, pady=(8, 2))

        ctk.CTkButton(btn_bar, text="全选", width=50, height=24,
                      font=ctk.CTkFont(family="Microsoft YaHei", size=10),
                      fg_color="transparent", border_width=1,
                      command=lambda: self._toggle_all(True)).pack(side="left", padx=(0, 4))
        ctk.CTkButton(btn_bar, text="取消", width=50, height=24,
                      font=ctk.CTkFont(family="Microsoft YaHei", size=10),
                      fg_color="transparent", border_width=1,
                      command=lambda: self._toggle_all(False)).pack(side="left")

        self.selected_count = ctk.CTkLabel(
            btn_bar, text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color="#3fb950",
        )
        self.selected_count.pack(side="left", padx=8)

        self.video_tree = ctk.CTkScrollableFrame(left)
        self.video_tree.pack(fill="both", expand=True, padx=5, pady=(2, 5))

        self.refresh_list_btn = ctk.CTkButton(
            left, text="刷新列表", height=26, width=80,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="transparent", border_width=1,
            command=self._refresh_video_list,
        )
        self.refresh_list_btn.pack(pady=(0, 8))

        # === 右侧：聊天区 ===
        right = ctk.CTkFrame(main)
        right.pack(side="left", fill="both", expand=True)

        self.video_label = ctk.CTkLabel(
            right, text="请从左侧勾选视频",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            anchor="w",
        )
        self.video_label.pack(fill="x", padx=10, pady=(8, 2))

        self.context_label = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color=None, anchor="w",
        )
        self.context_label.pack(fill="x", padx=10, pady=(0, 5))

        self.chat_box = ctk.CTkScrollableFrame(right)
        self.chat_box.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        input_frame = ctk.CTkFrame(right, fg_color="transparent")
        input_frame.pack(fill="x", padx=5, pady=(0, 8))

        self.question_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="输入你的问题...（Enter 发送）",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            height=34,
        )
        self.question_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.question_entry.bind("<Return>", lambda e: self._ask_question())

        self.ask_btn = ctk.CTkButton(
            input_frame, text="发送", height=34, width=70,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            command=self._ask_question,
        )
        self.ask_btn.pack(side="right")

        self.reset_btn = ctk.CTkButton(
            input_frame, text="新对话", height=34, width=70,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="transparent", border_width=1,
            command=self._reset_chat,
        )
        self.reset_btn.pack(side="right", padx=(0, 8))

        self.save_chat_btn = ctk.CTkButton(
            input_frame, text="保存对话", height=34, width=70,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            fg_color="transparent", border_width=1,
            command=self._save_chat,
        )
        self.save_chat_btn.pack(side="right", padx=(0, 8))

    # ===== 视频列表 =====
    def _toggle_up_section(self, frame, label):
        """折叠/展开UP主视频列表"""
        if frame.winfo_ismapped():
            frame.pack_forget()
            label.configure(text=label.cget("text").replace("▾", "▸"))
        else:
            frame.pack(fill="x", after=label)
            label.configure(text=label.cget("text").replace("▸", "▾"))

    def _refresh_video_list(self):
        """刷新视频列表"""
        for w in self.video_tree.winfo_children():
            w.destroy()
        self._check_vars.clear()

        self._all_videos = scan_processed_videos(self.config.output_dir)
        if not self._all_videos:
            ctk.CTkLabel(
                self.video_tree, text="暂无已处理的视频",
                font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                text_color=None,
            ).pack(pady=20)
            return

        for uploader, videos in sorted(self._all_videos.items()):
            # UP主标题行（可点击折叠/展开）
            up_label = ctk.CTkLabel(
                self.video_tree,
                text=f"▸ {uploader} ({len(videos)})",
                font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
                anchor="w",
                cursor="hand2",
            )
            up_label.pack(fill="x", pady=(6, 1))

            # 视频容器（默认隐藏）
            vid_frame = ctk.CTkFrame(self.video_tree, fg_color="transparent")
            # 初始不pack，默认折叠

            for v in videos:
                path_key = v["transcript_path"]
                var = ctk.BooleanVar(value=False)
                self._check_vars[path_key] = var

                row = ctk.CTkFrame(vid_frame, fg_color="transparent")
                row.pack(fill="x", pady=1, padx=(15, 0))

                cb = ctk.CTkCheckBox(
                    row, text="", variable=var,
                    width=20, checkbox_width=16, checkbox_height=16,
                    command=self._update_selection,
                )
                cb.pack(side="left")

                ctk.CTkLabel(
                    row, text=v["title"][:35],
                    font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                    anchor="w",
                ).pack(side="left")

            # 绑定点击事件
            up_label.bind(
                "<Button-1>",
                lambda e, f=vid_frame, l=up_label: self._toggle_up_section(f, l),
            )

        self._update_selection()

    def _toggle_all(self, checked: bool):
        for var in self._check_vars.values():
            var.set(checked)
        self._update_selection()

    def _update_selection(self):
        """更新选中计数和上下文"""
        selected = [path for path, var in self._check_vars.items() if var.get()]
        count = len(selected)
        self.selected_count.configure(text=f"已选 {count}" if count > 0 else "")

        if count == 0:
            self.video_label.configure(text="请从左侧勾选视频")
            self.context_label.configure(text="")
        else:
            # 收集选中视频的信息
            titles = []
            total_chars = 0
            for path_key in selected:
                for videos in self._all_videos.values():
                    for v in videos:
                        if v["transcript_path"] == path_key:
                            titles.append(v["title"][:30])
                            try:
                                with open(path_key, "r", encoding="utf-8") as f:
                                    total_chars += len(f.read())
                            except Exception:
                                pass
                            break

            self.video_label.configure(text=f"已选 {count} 个视频")
            self.context_label.configure(text=f"共计 {total_chars} 字 | {'; '.join(titles[:3])}{'...' if len(titles) > 3 else ''}")

    # ===== 聊天 =====
    def _add_chat_message(self, role: str, content: str):
        frame = ctk.CTkFrame(self.chat_box)
        frame.pack(fill="x", pady=3, padx=5)

        colors = {"系统": "#8b949e", "你": "#58a6ff", "AI": "#3fb950"}
        color = colors.get(role, "#e0e0e0")

        ctk.CTkLabel(
            frame, text=f"[{role}]",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11, weight="bold"),
            text_color=color, anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            frame, text=content,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            wraplength=480, anchor="w", justify="left",
        ).pack(anchor="w", padx=(15, 0))

    def _load_selected_transcripts(self) -> tuple:
        """加载选中视频的逐字稿，返回 (combined_text, titles_string)"""
        selected = [p for p, v in self._check_vars.items() if v.get()]
        parts = []
        titles = []

        for path_key in selected:
            for videos in self._all_videos.values():
                for v in videos:
                    if v["transcript_path"] == path_key:
                        titles.append(v["title"])
                        try:
                            with open(path_key, "r", encoding="utf-8") as f:
                                parts.append(f"【{v['title']}】\n{f.read()}")
                        except Exception:
                            pass
                        break

        combined = "\n\n---\n\n".join(parts)
        title_str = "、".join(titles[:5])
        if len(titles) > 5:
            title_str += f" 等 {len(titles)} 个视频"
        return combined, title_str

    def _ask_question(self):
        """发送问题"""
        question = self.question_entry.get().strip()
        if not question:
            return

        selected = [p for p, v in self._check_vars.items() if v.get()]
        if not selected:
            self._add_chat_message("系统", "请先从左侧勾选至少一个视频")
            return

        self.question_entry.delete(0, "end")
        self.ask_btn.configure(state="disabled", text="...")

        transcript, title_str = self._load_selected_transcripts()
        self._add_chat_message("你", question)

        def do():
            from src.pipeline.qa_engine import QAEngine
            if self._engine is None:
                self._engine = QAEngine(self.config)

            try:
                answer = self._engine.ask(
                    question=question,
                    transcript=transcript,
                    video_title=title_str,
                )
                self.after(0, lambda: self._add_chat_message("AI", answer))
            except Exception as e:
                self.after(0, lambda: self._add_chat_message("系统", f"错误: {e}"))
            finally:
                self.after(0, lambda: self.ask_btn.configure(state="normal", text="发送"))

        threading.Thread(target=do, daemon=True).start()

    def _reset_chat(self):
        """重置对话（需确认）"""
        if not self.chat_box.winfo_children():
            return

        confirm = ctk.CTkToplevel(self)
        confirm.title("确认")
        confirm.geometry("300x130")
        confirm.transient(self)
        confirm.grab_set()

        ctk.CTkLabel(
            confirm, text="确定要清空当前对话吗？",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13),
        ).pack(pady=(20, 15))

        btn_bar = ctk.CTkFrame(confirm, fg_color="transparent")
        btn_bar.pack()

        def do_reset():
            if self._engine:
                self._engine.reset()
            for w in self.chat_box.winfo_children():
                w.destroy()
            confirm.destroy()

        ctk.CTkButton(btn_bar, text="确定", width=60, height=28,
                      font=ctk.CTkFont(family="Microsoft YaHei", size=12),
                      fg_color="#f44336", hover_color="#c62828",
                      command=do_reset).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_bar, text="取消", width=60, height=28,
                      font=ctk.CTkFont(family="Microsoft YaHei", size=12),
                      fg_color="transparent", border_width=1,
                      command=confirm.destroy).pack(side="left")

    def _save_chat(self):
        """保存对话记录"""
        from tkinter import filedialog
        from datetime import datetime
        from pathlib import Path

        if not self.chat_box.winfo_children():
            return

        # 收集聊天内容
        lines = []
        for frame in self.chat_box.winfo_children():
            labels = [c for c in frame.winfo_children() if isinstance(c, ctk.CTkLabel)]
            for lb in labels:
                text = lb.cget("text")
                if text.startswith("[") and "]" in text[:6]:
                    lines.append(text + "\n")
                else:
                    lines.append(text + "\n\n")

        content = "".join(lines)
        if not content.strip():
            return

        default_name = f"AI问答_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            initialfile=default_name,
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")],
        )
        if file_path:
            Path(file_path).write_text(content, encoding="utf-8")
            self._add_chat_message("系统", f"对话已保存到 {file_path}")

    def poll_logs(self):
        try:
            while True:
                self.log_queue.get_nowait()
        except queue.Empty:
            pass
