"""
Bili Video Summarizer - 入口模块
B站视频转文字概述工具
"""
import sys
from pathlib import Path

# 将 src 父目录加入 path，支持直接运行
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

from src.config import Config
from src.utils.logger import setup_logger
from src.gui.app import App


def main():
    """应用入口"""
    print("=" * 50)
    print("  Bili Video Summarizer - B站视频转文字概述")
    print("=" * 50)
    print()

    # 加载配置
    config = Config.load()

    # 设置日志（控制台 + 文件）
    log_file = Path(__file__).parent.parent / "app.log"
    setup_logger(log_file=log_file)
    print(f"  日志文件: {log_file}")
    print(f"  输出目录: {config.output_dir}")
    print(f"  DeepSeek API: {'已配置' if config.is_api_configured else '未配置'}")
    print()

    # 启动 GUI
    print("  正在启动 GUI...")
    app = App(config)
    app.mainloop()


if __name__ == "__main__":
    main()
