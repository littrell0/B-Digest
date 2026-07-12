"""
自定义 GUI 组件
"""
import customtkinter as ctk
from datetime import datetime
from typing import List


class LogPanel(ctk.CTkFrame):
    """日志显示面板"""

    def __init__(self, master, max_lines: int = 500, **kwargs):
        super().__init__(master, **kwargs)
        self.max_lines = max_lines

        # 日志文本框
        self.text = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            wrap="word",
            state="disabled",
        )
        self.text.pack(fill="both", expand=True, padx=2, pady=2)

        # 配置文本标签颜色
        self.text.tag_config("INFO", foreground="#58a6ff")
        self.text.tag_config("SUCCESS", foreground="#3fb950")
        self.text.tag_config("WARNING", foreground="#d29922")
        self.text.tag_config("ERROR", foreground="#f85149")
        self.text.tag_config("TIMESTAMP", foreground="#8b949e")

        self._line_count = 0

    def add_log(self, level: str, message: str, timestamp: datetime = None):
        """添加一条日志"""
        if timestamp is None:
            timestamp = datetime.now()

        self.text.configure(state="normal")

        time_str = timestamp.strftime("%H:%M:%S")
        self.text.insert("end", f"[{time_str}] ", "TIMESTAMP")
        self.text.insert("end", f"[{level}] ", level)
        self.text.insert("end", f"{message}\n")

        # 限制日志行数
        self._line_count += 1
        if self._line_count > self.max_lines:
            # 删除最早的行
            self.text.delete("1.0", "2.0")
            self._line_count -= 1

        self.text.see("end")
        self.text.configure(state="disabled")

    def add_batch(self, entries: List[dict]):
        """批量添加日志"""
        for entry in entries:
            self.add_log(
                level=entry.get("level", "INFO"),
                message=entry.get("message", ""),
                timestamp=entry.get("timestamp"),
            )

    def clear(self):
        """清空日志"""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._line_count = 0

    def info(self, message: str):
        self.add_log("INFO", message)

    def success(self, message: str):
        self.add_log("SUCCESS", message)

    def warning(self, message: str):
        self.add_log("WARNING", message)

    def error(self, message: str):
        self.add_log("ERROR", message)


class ProgressBar(ctk.CTkFrame):
    """带标签的进度条"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.status_label = ctk.CTkLabel(
            self,
            text="就绪",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=5, pady=(5, 0))

        self.bar = ctk.CTkProgressBar(self)
        self.bar.pack(fill="x", padx=5, pady=(2, 5))
        self.bar.set(0)

    def update(self, percent: int, status: str = ""):
        """更新进度"""
        self.bar.set(percent / 100.0)
        if status:
            self.status_label.configure(text=status)
        else:
            self.status_label.configure(text=f"进度: {percent}%")

    def reset(self):
        """重置"""
        self.bar.set(0)
        self.status_label.configure(text="就绪")


class ProcessButton(ctk.CTkButton):
    """处理按钮 - 带运行/停止状态切换"""

    def __init__(self, master, command=None, **kwargs):
        super().__init__(
            master,
            text="开始处理",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
            height=36,
            command=command,
            **kwargs,
        )
        self._is_processing = False

    @property
    def is_processing(self) -> bool:
        return self._is_processing

    def set_processing(self, processing: bool):
        """设置处理状态"""
        self._is_processing = processing
        if processing:
            self.configure(
                text="处理中...",
                state="disabled",
                fg_color="#555555",
            )
        else:
            self.configure(
                text="开始处理",
                state="normal",
                fg_color="#6c63ff",
            )


class URLInput(ctk.CTkFrame):
    """URL输入框"""

    def __init__(self, master, on_process=None, **kwargs):
        super().__init__(master, **kwargs)

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="请输入B站视频链接，如: https://www.bilibili.com/video/BV1xx411c7mD",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            height=38,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.button = ProcessButton(
            self,
            command=on_process,
        )
        self.button.pack(side="right")

    def get_url(self) -> str:
        """获取输入的URL"""
        return self.entry.get().strip()

    def set_url(self, url: str):
        """设置URL"""
        self.entry.delete(0, "end")
        self.entry.insert(0, url)

    def set_processing(self, processing: bool):
        self.button.set_processing(processing)


class InfoCard(ctk.CTkFrame):
    """视频信息卡片"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.title_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold"),
            anchor="w",
        )
        self.title_label.pack(fill="x", padx=10, pady=(10, 5))

        self.info_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            anchor="w",
            text_color="#8b949e",
        )
        self.info_label.pack(fill="x", padx=10, pady=(0, 10))

    def set_info(self, title: str, info: str):
        """设置信息"""
        self.title_label.configure(text=title)
        self.info_label.configure(text=info)

    def clear(self):
        """清空"""
        self.title_label.configure(text="")
        self.info_label.configure(text="")
