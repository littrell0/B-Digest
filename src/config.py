"""
配置管理模块 - 从环境变量和本地文件加载应用设置
优先级: 环境变量 > settings.json > 默认值
"""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# 默认配置值
DEFAULTS = {
    "api_key": "",
    "api_base_url": "https://api.deepseek.com",
    "api_model": "deepseek-v4-flash",
    "whisper_model": "small",
    "whisper_device": "cpu",
    "whisper_compute_type": "int8",
    "bili_sessdata": "",
    "bili_bili_jct": "",
    "bili_buvid3": "",
    "output_dir": "./output",
    "theme": "dark",
    "hf_endpoint": "https://hf-mirror.com",
    "model_dir": "./models",
    "summary_detail": "精细概览",
    "output_format": "markdown",
}


@dataclass
class Config:
    """应用配置类"""

    # DeepSeek API
    api_key: str = ""
    api_base_url: str = "https://api.deepseek.com"
    api_model: str = "deepseek-v4-flash"

    # 语音识别
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # B站账号
    bili_sessdata: str = ""
    bili_bili_jct: str = ""
    bili_buvid3: str = ""

    # 输出
    output_dir: str = "./output"

    # 界面
    theme: str = "dark"

    # HuggingFace 镜像（国内加速）
    hf_endpoint: str = "https://hf-mirror.com"

    # 本地模型目录
    model_dir: str = "./models"

    # 概览详细程度
    summary_detail: str = "大致概览"

    # 排除的UP主UID列表（逗号分隔）
    excluded_uids: str = ""

    # 输出格式
    output_format: str = "markdown"

    _settings_path: Optional[Path] = field(default=None, repr=False)

    @classmethod
    def load(cls, settings_path: Optional[Path] = None) -> "Config":
        """
        加载配置，优先级: 环境变量 > settings.json > 默认值

        Args:
            settings_path: settings.json 的路径，默认为项目根目录
        """
        config = cls()

        # 1. 先应用默认值
        for key, value in DEFAULTS.items():
            setattr(config, key, value)

        # 2. 从 settings.json 加载
        if settings_path is None:
            settings_path = Path(__file__).parent.parent / "settings.json"
        config._settings_path = settings_path

        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for key, value in saved.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            except (json.JSONDecodeError, IOError):
                pass  # 配置文件损坏时忽略

        # 3. 先从 .env 文件加载到 os.environ
        config._load_dotenv()

        # 4. 从环境变量覆盖 (最高优先级: 系统环境变量 > .env > settings.json)
        env_map = {
            "API_KEY": "api_key",
            "API_BASE_URL": "api_base_url",
            "API_MODEL": "api_model",
            # 向后兼容旧名称
            "DEEPSEEK_API_KEY": "api_key",
            "DEEPSEEK_BASE_URL": "api_base_url",
            "DEEPSEEK_MODEL": "api_model",
            # 其他
            "WHISPER_MODEL": "whisper_model",
            "WHISPER_DEVICE": "whisper_device",
            "BILI_SESSDATA": "bili_sessdata",
            "BILI_BILI_JCT": "bili_bili_jct",
            "BILI_BUVID3": "bili_buvid3",
            "OUTPUT_DIR": "output_dir",
            "HF_ENDPOINT": "hf_endpoint",
            "MODEL_DIR": "model_dir",
        }
        for env_key, attr_name in env_map.items():
            env_val = os.environ.get(env_key)
            if env_val:
                setattr(config, attr_name, env_val)

        # 向后兼容：settings.json 中可能有旧字段名
        for old_key, new_key in [
            ("deepseek_api_key", "api_key"),
            ("deepseek_base_url", "api_base_url"),
            ("deepseek_model", "api_model"),
        ]:
            if hasattr(config, old_key):
                old_val = getattr(config, old_key)
                if old_val and not getattr(config, new_key):
                    setattr(config, new_key, old_val)

        # 向后兼容：DeepSeek 已于 2026-07-24 废弃 deepseek-chat，自动迁移到 V4 Flash
        if config.api_model == "deepseek-chat":
            config.api_model = "deepseek-v4-flash"

        return config

    def _load_dotenv(self) -> None:
        """尝试从 .env 文件加载环境变量"""
        env_file = Path(__file__).parent.parent / ".env"
        if not env_file.exists():
            return

        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ.setdefault(key, value)
        except IOError:
            pass

    def save(self) -> None:
        """保存配置到 settings.json（文件不存在时自动创建）"""
        if self._settings_path is None:
            self._settings_path = Path(__file__).parent.parent / "settings.json"

        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        with open(self._settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def to_dict(self) -> dict:
        """转为字典（排除私有字段）"""
        return {k: v for k, v in asdict(self).items() if not k.startswith("_")}

    @property
    def is_api_configured(self) -> bool:
        """检查是否配置了 DeepSeek API Key"""
        return bool(self.api_key)

    @property
    def is_bili_configured(self) -> bool:
        """检查是否配置了 B站账号"""
        return bool(self.bili_sessdata and self.bili_bili_jct)
