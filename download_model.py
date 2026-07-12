"""
下载 faster-whisper 模型到本地 models/ 目录
使用 ModelScope (魔搭社区) - 国内高速下载
"""
import sys
import time
from pathlib import Path

MODEL_SIZE = "large-v3"
LOCAL_DIR = Path(__file__).parent / "models" / f"faster-whisper-{MODEL_SIZE}"


def main():
    print(f"下载 faster-whisper {MODEL_SIZE} 模型")
    print(f"来源: ModelScope (阿里魔搭社区)")
    print(f"目标: {LOCAL_DIR}")
    print()

    try:
        from modelscope import snapshot_download
    except ImportError:
        print("请先安装 modelscope: pip install modelscope")
        sys.exit(1)

    repo_id = f"keepitsimple/faster-whisper-{MODEL_SIZE}"

    start = time.time()
    try:
        local_path = snapshot_download(repo_id, local_dir=str(LOCAL_DIR))
        elapsed = time.time() - start
        total = sum(f.stat().st_size for f in Path(local_path).rglob("*") if f.is_file())
        print(f"\n下载完成！")
        print(f"  耗时: {elapsed:.0f} 秒")
        print(f"  大小: {total / 1e9:.2f} GB")
        print(f"  路径: {local_path}")
    except Exception as e:
        print(f"下载失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
