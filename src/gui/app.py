"""
主应用窗口
"""
import queue
import customtkinter as ctk

from src.config import Config
from src.gui.styles import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT
from src.gui.single_video_tab import SingleVideoTab
from src.gui.batch_tab import BatchTab
from src.gui.qa_tab import QATab
from src.gui.settings_tab import SettingsTab


class App(ctk.CTk):
    """Bili Video Summarizer 主窗口"""

    def __init__(self, config: Config):
        super().__init__()

        self.config = config
        self.log_queue = queue.Queue()

        # 设置外观
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 窗口配置
        self.title("Bili Video Summarizer - B站视频转文字概述")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # 居中显示
        self._center_window()

        # 构建界面
        self._build_ui()

        # 绑定快捷键
        self._bind_shortcuts()

        # 启动日志轮询
        self._poll_logs()

    def _center_window(self):
        """窗口居中显示（首次启动），或恢复上次位置"""
        if self.config._settings_path and self.config._settings_path.exists():
            try:
                import json
                with open(self.config._settings_path, "r") as f:
                    saved = json.load(f)
                geo = saved.get("_window_geo", "")
                if geo:
                    self.geometry(geo)
                    return
            except Exception:
                pass
        # 默认居中
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        """构建主界面"""
        # 配置网格
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Tab 视图
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # 添加 Tab
        self.tab_view.add("单视频处理")
        self.tab_view.add("批量处理")
        self.tab_view.add("AI 问答")
        self.tab_view.add("设置")

        # 单视频处理 Tab
        self.single_tab = SingleVideoTab(
            self.tab_view.tab("单视频处理"),
            config=self.config,
            log_queue=self.log_queue,
        )
        self.single_tab.pack(fill="both", expand=True)

        # 批量处理 Tab
        self.batch_tab = BatchTab(
            self.tab_view.tab("批量处理"),
            config=self.config,
            log_queue=self.log_queue,
        )
        self.batch_tab.pack(fill="both", expand=True)

        # AI 问答 Tab
        self.qa_tab = QATab(
            self.tab_view.tab("AI 问答"),
            config=self.config,
            log_queue=self.log_queue,
        )
        self.qa_tab.pack(fill="both", expand=True)

        # 设置 Tab
        self.settings_tab_page = SettingsTab(
            self.tab_view.tab("设置"),
            config=self.config,
        )
        self.settings_tab_page.pack(fill="both", expand=True)

        # 默认选中第一个Tab
        self.tab_view.set("单视频处理")

    def _bind_shortcuts(self):
        """绑定键盘快捷键"""
        # Ctrl+Q 退出
        self.bind("<Control-q>", lambda e: self.quit())
        self.bind("<Control-w>", lambda e: self.quit())

    def _poll_logs(self):
        """定时轮询日志队列"""
        if hasattr(self, 'single_tab'):
            self.single_tab.poll_logs()
        if hasattr(self, 'batch_tab'):
            self.batch_tab.poll_logs()
        if hasattr(self, 'qa_tab'):
            self.qa_tab.poll_logs()

        self.after(200, self._poll_logs)

    def quit(self):
        """退出应用（保存窗口位置）"""
        try:
            geo = self.geometry()
            import json
            if self.config._settings_path and self.config._settings_path.exists():
                with open(self.config._settings_path, "r") as f:
                    saved = json.load(f)
            else:
                saved = {}
            saved["_window_geo"] = geo
            with open(self.config._settings_path, "w", encoding="utf-8") as f:
                json.dump(saved, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        self.destroy()
