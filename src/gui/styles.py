"""
GUI 样式和主题配置
"""
from typing import Dict


# 颜色方案
DARK_THEME = {
    "bg": "#1a1a2e",
    "fg": "#e0e0e0",
    "accent": "#6c63ff",
    "accent_hover": "#5a52d5",
    "success": "#4caf50",
    "warning": "#ff9800",
    "error": "#f44336",
    "card_bg": "#16213e",
    "card_border": "#2a2a4a",
    "input_bg": "#0f3460",
    "input_fg": "#e0e0e0",
    "log_bg": "#0d1117",
    "log_fg": "#c9d1d9",
    "progress_bg": "#2a2a4a",
    "tab_bg": "#16213e",
    "tab_active": "#6c63ff",
}

LIGHT_THEME = {
    "bg": "#fdf0f4",        # 淡粉底色（来自图标淡粉调）
    "fg": "#4a3340",        # 深棕粉文字
    "accent": "#f07890",    # 图标粉色
    "accent_hover": "#d06078",
    "success": "#4caf50",
    "warning": "#ff9800",
    "error": "#f44336",
    "card_bg": "#fff5f7",   # 微粉卡片
    "card_border": "#f5d0d8",
    "input_bg": "#ffffff",
    "input_fg": "#4a3340",
    "log_bg": "#fffafb",
    "log_fg": "#4a3340",
    "progress_bg": "#f5dde2",
    "tab_bg": "#fde8ed",
    "tab_active": "#f07890",
}


def get_theme(theme_name: str = "dark") -> Dict[str, str]:
    """获取主题颜色字典"""
    if theme_name == "light":
        return LIGHT_THEME
    return DARK_THEME


# 字体配置
FONT_FAMILY = "Microsoft YaHei"
FONT_FAMILY_MONO = "Cascadia Code"

FONT_SIZES = {
    "title": 18,
    "heading": 14,
    "body": 12,
    "small": 10,
    "mono": 11,
}

# 窗口默认尺寸
WINDOW_WIDTH = 860
WINDOW_HEIGHT = 680
WINDOW_MIN_WIDTH = 640
WINDOW_MIN_HEIGHT = 500
