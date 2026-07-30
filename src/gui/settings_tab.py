"""
设置 Tab
"""
import threading
import customtkinter as ctk
from pathlib import Path

from src.config import Config

# API 模型预设
API_MODELS = {
    "deepseek-chat": {
        "base_url": "https://api.deepseek.com",
        "desc": "DeepSeek V3 · 准确 8.5 速度 8 · 适用于 platform.deepseek.com 的 API Key",
    },
    "deepseek-v4-pro": {
        "base_url": "https://api.deepseek.com",
        "desc": "DeepSeek V4 Pro · 准确 9 速度 8 · 适用于特定端点的 API Key",
    },
    "deepseek-v4-flash": {
        "base_url": "https://api.deepseek.com",
        "desc": "DeepSeek V4 Flash · 准确 8.5 速度 9 · 适用于特定端点的 API Key",
    },
    "qwen-plus": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "desc": "通义千问 Qwen-Plus · 准确 8 速度 7.5 · 中文最自然，月送500万Token",
    },
    "glm-4-flash": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "desc": "智谱 GLM-4-Flash · 准确 7.5 速度 9 · 永久免费，日常够用",
    },
}


class SettingsTab(ctk.CTkFrame):
    """设置页面"""

    def __init__(self, master, config: Config, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config

        # 可滚动容器
        self.scroll = ctk.CTkScrollableFrame(
            self,
            label_text="设置",
            label_font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold"),
        )
        self.scroll.pack(fill="both", expand=True)

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        """构建界面（内容放在 scroll 内）"""

        # === 顶部操作按钮 ===
        btn_bar = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_bar.pack(fill="x", padx=10, pady=(10, 10))

        self.save_btn = ctk.CTkButton(
            btn_bar,
            text="保存设置",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            height=36,
            width=120,
            command=self._save_settings,
        )
        self.save_btn.pack(side="left", padx=(0, 8))

        self.cancel_btn = ctk.CTkButton(
            btn_bar,
            text="取消更改",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=36,
            width=100,
            fg_color="transparent",
            border_width=1,
            command=self._cancel_changes,
        )
        self.cancel_btn.pack(side="left", padx=(0, 8))

        self.reset_btn = ctk.CTkButton(
            btn_bar,
            text="恢复默认",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=36,
            width=100,
            fg_color="transparent",
            border_width=1,
            command=self._reset_settings,
        )
        self.reset_btn.pack(side="left")

        self.save_status = ctk.CTkLabel(
            btn_bar,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
        )
        self.save_status.pack(side="left", padx=15)

        # === DeepSeek API 设置 ===
        api_card = self._create_section("AI 模型设置")

        # 模型选择
        model_sel_frame = ctk.CTkFrame(api_card, fg_color="transparent")
        model_sel_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            model_sel_frame, text="模型",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        ).pack(side="left")

        self.api_preset_var = ctk.StringVar(value="deepseek-chat")
        self.api_preset_menu = ctk.CTkOptionMenu(
            model_sel_frame,
            values=list(API_MODELS.keys()),
            variable=self.api_preset_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=200,
            command=self._on_api_preset_changed,
        )
        self.api_preset_menu.pack(side="left")

        # 模型简介
        self.api_model_desc = ctk.CTkLabel(
            api_card,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color=None,
            anchor="w",
        )
        self.api_model_desc.pack(fill="x", padx=10, pady=(0, 5))

        # API Key
        key_frame = ctk.CTkFrame(api_card, fg_color="transparent")
        key_frame.pack(fill="x", padx=10, pady=(5, 5))

        ctk.CTkLabel(
            key_frame, text="API Key",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        ).pack(side="left")

        self.api_key_entry = ctk.CTkEntry(
            key_frame, placeholder_text="sk-...",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            show="*",
        )
        self.api_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.test_btn = ctk.CTkButton(
            key_frame, text="测试连接",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30, width=80,
            command=self._test_connection,
        )
        self.test_btn.pack(side="right")

        # Base URL（预设自动填，自定义时显示）
        self.url_frame = ctk.CTkFrame(api_card, fg_color="transparent")
        self.url_frame.pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkLabel(
            self.url_frame, text="Base URL",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        ).pack(side="left")

        self.base_url_entry = ctk.CTkEntry(
            self.url_frame,
            placeholder_text="https://api.deepseek.com",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
        )
        self.base_url_entry.pack(side="left", fill="x", expand=True)

        # 测试状态
        self.test_status = ctk.CTkLabel(
            api_card,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
        )
        self.test_status.pack(anchor="w", padx=10, pady=(5, 10))

        # 概览详细程度
        summary_frame = ctk.CTkFrame(api_card, fg_color="transparent")
        summary_frame.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkLabel(
            summary_frame,
            text="概览详细程度",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        ).pack(side="left")

        self.summary_detail_var = ctk.StringVar(value="大致概览")
        self.summary_menu = ctk.CTkOptionMenu(
            summary_frame,
            values=["精细概览", "大致概览", "极简概览"],
            variable=self.summary_detail_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self._on_summary_detail_changed,
            width=100,
        )
        self.summary_menu.pack(side="left", padx=(0, 10))

        self.summary_detail_info = ctk.CTkLabel(
            summary_frame,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color=None,
        )
        self.summary_detail_info.pack(side="left")

        # === 语音识别设置 ===
        asr_card = self._create_section("语音识别设置")

        # 精确度预设
        preset_frame = ctk.CTkFrame(asr_card, fg_color="transparent")
        preset_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            preset_frame,
            text="识别精确度",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        ).pack(side="left")

        self.preset_var = ctk.StringVar(value="最精确")
        self.preset_menu = ctk.CTkOptionMenu(
            preset_frame,
            values=["最精确", "精确", "普通", "急速"],
            variable=self.preset_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self._on_preset_changed,
            width=100,
        )
        self.preset_menu.pack(side="left", padx=(0, 10))

        # 预设详细信息（第二行）
        self.preset_info = ctk.CTkLabel(
            asr_card,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color=None,
            anchor="w",
        )
        self.preset_info.pack(fill="x", padx=10, pady=(0, 5))

        # 隐藏的 model_var（同步预设值用）
        self.model_var = ctk.StringVar(value="large-v3")

        # 模型下载按钮 + 进度条
        dl_frame = ctk.CTkFrame(asr_card, fg_color="transparent")
        dl_frame.pack(fill="x", padx=10, pady=(8, 5))

        self.download_btn = ctk.CTkButton(
            dl_frame,
            text="检查中...",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30,
            width=90,
            command=self._download_model,
        )
        self.download_btn.pack(side="left")

        # 下载进度条
        self.model_progress = ctk.CTkProgressBar(asr_card)
        self.model_progress.pack(fill="x", padx=10, pady=(5, 2))
        self.model_progress.set(0)

        self.model_progress_label = ctk.CTkLabel(
            asr_card,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color=None,
        )
        self.model_progress_label.pack(anchor="w", padx=10, pady=(0, 5))

        model_hint = ctk.CTkLabel(
            asr_card,
            text="推荐 large-v3，约 3GB。点击上方按钮可提前下载，处理视频时无需等待",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color=None,
        )
        model_hint.pack(anchor="w", padx=10, pady=(0, 10))

        # === 输出设置 ===
        output_card = self._create_section("输出设置")

        out_frame = ctk.CTkFrame(output_card, fg_color="transparent")
        out_frame.pack(fill="x", padx=10, pady=(10, 10))

        ctk.CTkLabel(
            out_frame,
            text="输出目录",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        ).pack(side="left")

        self.output_dir_entry = ctk.CTkEntry(
            out_frame,
            placeholder_text="./output",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
        )
        self.output_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.browse_btn = ctk.CTkButton(
            out_frame,
            text="浏览...",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30,
            width=60,
            command=self._browse_output_dir,
        )
        self.browse_btn.pack(side="right")

        # 输出格式
        fmt_frame = ctk.CTkFrame(output_card, fg_color="transparent")
        fmt_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            fmt_frame, text="输出格式",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        ).pack(side="left")

        self.output_fmt_var = ctk.StringVar(value="markdown")
        self.output_fmt_menu = ctk.CTkOptionMenu(
            fmt_frame,
            values=["markdown", "txt"],
            variable=self.output_fmt_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        )
        self.output_fmt_menu.pack(side="left")

        ctk.CTkLabel(
            fmt_frame, text="markdown=带格式  txt=纯文本",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color=None,
        ).pack(side="left", padx=8)

        # === 界面设置 ===
        ui_card = self._create_section("界面设置")

        theme_frame = ctk.CTkFrame(ui_card, fg_color="transparent")
        theme_frame.pack(fill="x", padx=10, pady=(10, 10))

        ctk.CTkLabel(
            theme_frame, text="主题",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        ).pack(side="left")

        self.theme_var = ctk.StringVar(value=self.config.theme)
        self.theme_menu = ctk.CTkOptionMenu(
            theme_frame,
            values=["dark", "light (测试中)"],
            variable=self.theme_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=80,
            command=self._on_theme_changed,
        )
        self.theme_menu.pack(side="left")

        # === B站账号设置 ===
        bili_card = self._create_section("B站账号 (可选，用于批量处理)")

        bili_hint = ctk.CTkLabel(
            bili_card,
            text="在浏览器中登录B站后，从Cookie中获取以下信息",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color=None,
        )
        bili_hint.pack(anchor="w", padx=10, pady=(10, 5))

        fields = [
            ("SESSDATA", "sessdata_entry"),
            ("bili_jct", "jct_entry"),
            ("buvid3", "buvid3_entry"),
        ]
        for label, attr_name in fields:
            self._create_labeled_entry(bili_card, label, attr_name, show="*")

        # 查看日志
        log_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        log_frame.pack(fill="x", padx=10, pady=(5, 15))

        ctk.CTkButton(
            log_frame, text="查看运行日志",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            height=30, width=120,
            fg_color="transparent", border_width=1,
            command=self._open_log_file,
        ).pack(side="left")

        # (按钮已移至顶部)

    def _create_section(self, title: str) -> ctk.CTkFrame:
        """创建设置分区"""
        frame = ctk.CTkFrame(self.scroll)
        frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        return frame

    def _create_labeled_entry(self, parent, label: str, attr_name: str, show: str = ""):
        """创建带标签的输入框"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=3)

        ctk.CTkLabel(
            frame,
            text=label,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            width=100,
        ).pack(side="left")

        entry = ctk.CTkEntry(
            frame,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            show=show,
        )
        entry.pack(side="left", fill="x", expand=True)
        setattr(self, attr_name, entry)

    def _load_config(self):
        """加载当前配置到UI"""
        self.api_key_entry.insert(0, self.config.api_key)
        self.base_url_entry.insert(0, self.config.api_base_url)
        # 同步模型预设
        self._sync_api_preset()
        self._update_api_model_desc()
        self.model_var.set(self.config.whisper_model)
        self.output_dir_entry.insert(0, self.config.output_dir)
        self.output_fmt_var.set(self.config.output_format or "markdown")
        self.summary_detail_var.set(self.config.summary_detail or "精细概览")
        t = self.config.theme or "dark"
        self.theme_var.set(t if t == "dark" else "light (测试中)")
        self._update_summary_detail_info()

        if self.config.bili_sessdata:
            self.sessdata_entry.insert(0, self.config.bili_sessdata)
        if self.config.bili_bili_jct:
            self.jct_entry.insert(0, self.config.bili_bili_jct)
        if self.config.bili_buvid3:
            self.buvid3_entry.insert(0, self.config.bili_buvid3)

        # 同步预设
        self._sync_preset_from_model()
        self._update_preset_scores()

        # 检查模型下载状态
        self.after(300, self._refresh_download_btn)

    def _sync_preset_from_model(self):
        """根据当前模型同步预设选择"""
        from src.pipeline.asr_engine import ACCURACY_PRESETS
        model = self.model_var.get()
        for preset_name, info in ACCURACY_PRESETS.items():
            if info["model"] == model:
                self.preset_var.set(preset_name)
                return
        self.preset_var.set("")  # 自定义模型

    def _on_preset_changed(self, choice: str):
        """预设改变 → 同步模型（需保存才生效）"""
        from src.pipeline.asr_engine import ACCURACY_PRESETS
        if choice in ACCURACY_PRESETS:
            model = ACCURACY_PRESETS[choice]["model"]
            self.model_var.set(model)
        self._update_preset_scores()

    def _sync_api_preset(self):
        """根据当前 model 匹配预设下拉"""
        model = self.config.api_model or "deepseek-chat"
        if model in API_MODELS:
            self.api_preset_var.set(model)
        else:
            self.api_preset_var.set("deepseek-chat")
        self._update_api_model_desc()

    def _on_api_preset_changed(self, choice: str):
        """模型改变 → 自动填入 Base URL"""
        if choice in API_MODELS:
            self.base_url_entry.delete(0, "end")
            self.base_url_entry.insert(0, API_MODELS[choice]["base_url"])
        self._update_api_model_desc()

    def _update_api_model_desc(self):
        """更新模型简介"""
        choice = self.api_preset_var.get()
        if choice in API_MODELS:
            self.api_model_desc.configure(text=API_MODELS[choice]["desc"])

    def _on_summary_detail_changed(self, choice: str):
        """概览详细程度改变（需保存才生效）"""
        self._update_summary_detail_info()

    def _on_theme_changed(self, choice: str):
        """主题切换立即生效"""
        import customtkinter as ctk
        import logging
        logger = logging.getLogger("bili_summarizer")
        mode = "dark" if choice == "dark" else "light"
        logger.info(f"Theme switch to: {mode}")
        ctk.set_appearance_mode(mode)
        ctk.set_default_color_theme("dark-blue" if mode == "dark" else "blue")
        self.config.theme = mode
        logger.info(f"Theme set done: appearance={ctk.get_appearance_mode()}")

    def _update_summary_detail_info(self):
        """更新概览详细程度说明"""
        from src.pipeline.summarizer import SUMMARY_DETAIL_CONFIG
        detail = self.summary_detail_var.get()
        if detail in SUMMARY_DETAIL_CONFIG:
            cfg = SUMMARY_DETAIL_CONFIG[detail]
            cap = f"，上限{cfg['max_chars']}字" if cfg["max_chars"] else ""
            self.summary_detail_info.configure(
                text=f"原文 {cfg['ratio']}{cap} · {cfg['desc']}"
            )

    def _update_preset_scores(self):
        """更新预设评分显示"""
        from src.pipeline.asr_engine import ACCURACY_PRESETS
        preset = self.preset_var.get()
        if preset in ACCURACY_PRESETS:
            info = ACCURACY_PRESETS[preset]
            note = info.get("note", "")
            self.preset_info.configure(
                text=f"模型: {info['model']}  |  精确度: {info['accuracy_pct']}  |  速度: {info['speed_per_min']} / 每分钟视频  |  适合: {info['scene']} {note}"
            )
        else:
            self.preset_info.configure(text="")

    def _save_settings(self):
        """保存设置（所有修改一次性生效）"""
        self.config.api_key = self.api_key_entry.get().strip()
        self.config.api_base_url = self.base_url_entry.get().strip() or "https://api.deepseek.com"
        self.config.api_model = self.api_preset_var.get()
        self.config.whisper_model = self.model_var.get()
        self.config.summary_detail = self.summary_detail_var.get()
        self.config.output_dir = self.output_dir_entry.get().strip() or "./output"
        self.config.output_format = self.output_fmt_var.get()
        t = self.theme_var.get()
        self.config.theme = "dark" if t == "dark" else "light"

        # 直接读取 B站 Cookie 输入框
        if hasattr(self, "sessdata_entry"):
            self.config.bili_sessdata = self.sessdata_entry.get().strip()
        if hasattr(self, "jct_entry"):
            self.config.bili_bili_jct = self.jct_entry.get().strip()
        if hasattr(self, "buvid3_entry"):
            self.config.bili_buvid3 = self.buvid3_entry.get().strip()

        # 调试输出
        print(f"[DEBUG] Saving: sessdata={self.config.bili_sessdata[:10] if self.config.bili_sessdata else '(empty)'}... jct={self.config.bili_bili_jct[:10] if self.config.bili_bili_jct else '(empty)'}...")

        try:
            self.config.save()
            print(f"[DEBUG] Saved to: {self.config._settings_path}")
            self.save_status.configure(text="✓ 设置已保存", text_color="#3fb950")
            self.after(3000, lambda: self.save_status.configure(text=""))
        except Exception as e:
            print(f"[DEBUG] Save error: {e}")
            self.save_status.configure(text=f"保存失败: {e}", text_color="#f85149")

    def _cancel_changes(self):
        """取消更改，重新加载已保存的配置"""
        self.config = Config.load(self.config._settings_path)
        # 清空所有输入框并重新加载
        self._reload_all_ui()
        self.save_status.configure(text="已恢复为上次保存的设置", text_color="#d29922")
        self.after(3000, lambda: self.save_status.configure(text=""))

    def _reload_all_ui(self):
        """重新加载所有 UI 控件"""
        self.api_key_entry.delete(0, "end")
        self.base_url_entry.delete(0, "end")
        self.output_dir_entry.delete(0, "end")
        for name in ["sessdata_entry", "jct_entry", "buvid3_entry"]:
            if hasattr(self, name):
                getattr(self, name).delete(0, "end")
        self._load_config()

    def _reset_settings(self):
        """恢复默认设置"""
        from src.config import DEFAULTS

        self.api_key_entry.delete(0, "end")
        self.base_url_entry.delete(0, "end")
        self.base_url_entry.insert(0, DEFAULTS["api_base_url"])
        self.model_var.set(DEFAULTS["whisper_model"])
        self.summary_detail_var.set(DEFAULTS["summary_detail"])
        self.output_dir_entry.delete(0, "end")
        self.output_dir_entry.insert(0, DEFAULTS["output_dir"])
        self._update_preset_scores()
        self._update_summary_detail_info()

        self.save_status.configure(text="已恢复默认值（需点击保存）", text_color="#d29922")

    def _test_connection(self):
        """测试 DeepSeek API 连接"""
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            self.test_status.configure(text="请先输入 API Key", text_color="#f85149")
            return

        self.test_btn.configure(state="disabled", text="测试中...")
        self.test_status.configure(text="正在测试连接...", text_color="#d29922")

        def do_test():
            try:
                from openai import OpenAI
                base_url = self.base_url_entry.get().strip() or "https://api.deepseek.com"
                client = OpenAI(api_key=api_key, base_url=base_url)
                client.models.list()
                self.after(0, lambda: self._on_test_result(True, "连接成功 ✓"))
            except Exception as e:
                self.after(0, lambda: self._on_test_result(False, f"连接失败: {e}"))

        thread = threading.Thread(target=do_test, daemon=True)
        thread.start()

    def _on_test_result(self, success: bool, message: str):
        """测试结果回调"""
        self.test_btn.configure(state="normal", text="测试连接")
        color = "#3fb950" if success else "#f85149"
        self.test_status.configure(text=message, text_color=color)

    def _refresh_download_btn(self):
        """更新下载按钮状态"""
        try:
            from src.pipeline.asr_engine import ASREngine
            asr = ASREngine(self.config)
            model_size = self.model_var.get()
            if asr.is_available() and asr.is_model_downloaded(model_size):
                self.download_btn.configure(text="重新下载", state="normal")
            else:
                self.download_btn.configure(text="下载模型", state="normal")
        except Exception:
            self.download_btn.configure(text="下载模型", state="normal")

    def _download_model(self):
        """下载语音识别模型"""
        model_size = self.model_var.get()

        self.download_btn.configure(state="disabled", text="下载中...")
        self.model_progress.set(0)
        self.model_progress_label.configure(text="准备下载...")

        def do_download():
            try:
                from src.pipeline.asr_engine import ASREngine
                asr = ASREngine(self.config)

                def progress(pct: int, msg: str):
                    self.after(0, lambda: self.model_progress.set(pct / 100.0))
                    self.after(0, lambda: self.model_progress_label.configure(text=f"{msg} ({pct}%)"))

                asr.download_model(
                    model_size=model_size,
                    progress_callback=progress,
                )

                self.after(0, lambda: self._on_download_finished(True, f"{model_size} 下载完成"))
            except Exception as e:
                self.after(0, lambda: self._on_download_finished(False, f"下载失败: {e}"))

        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()

    def _on_download_finished(self, success: bool, message: str):
        """模型下载完成回调"""
        if success:
            self.model_progress.set(1.0)
            self.download_btn.configure(text="重新下载", state="normal")
        else:
            self.model_progress.set(0)
            self.download_btn.configure(text="下载模型", state="normal")
        self.model_progress_label.configure(text=message)

    def _open_log_file(self):
        """打开日志文件"""
        import subprocess, os
        from pathlib import Path
        log_path = Path(__file__).parent.parent.parent / "app.log"
        if log_path.exists():
            os.startfile(str(log_path))
        else:
            self.save_status.configure(text="日志文件不存在", text_color="#f85149")

    def _browse_output_dir(self):
        """浏览输出目录"""
        from tkinter import filedialog
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, dir_path)
