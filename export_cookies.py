"""
从 Edge/Chrome 浏览器直接读取 B站 Cookie
无需任何扩展，一键导出
"""
import os
import sys
import shutil
import tempfile
import sqlite3
from pathlib import Path


def find_edge_cookie_db() -> Path | None:
    """查找 Edge 的 Cookie 数据库路径"""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    paths = [
        Path(localappdata) / "Microsoft/Edge/User Data/Default/Network/Cookies",
        Path(localappdata) / "Microsoft/Edge/User Data/Default/Cookies",
        Path(localappdata) / "Google/Chrome/User Data/Default/Network/Cookies",
        Path(localappdata) / "Google/Chrome/User Data/Default/Cookies",
    ]
    for p in paths:
        if p.exists():
            return p
    return None


def export_cookies(domain: str = "bilibili.com", output: str = "cookies.txt"):
    """从浏览器数据库导出指定域名的 Cookie 为 Netscape 格式"""
    db_path = find_edge_cookie_db()
    if not db_path:
        print("未找到 Edge/Chrome Cookie 数据库")
        print("请确保浏览器已安装且登录了B站")
        return False

    print(f"找到 Cookie 数据库: {db_path}")

    # 浏览器运行时数据库被锁定，需要复制
    tmp = Path(tempfile.gettempdir()) / "cookies_temp.db"
    shutil.copy2(db_path, tmp)

    try:
        conn = sqlite3.connect(str(tmp))
        cursor = conn.cursor()

        # 查询 bilibili.com 相关的所有 cookie
        cursor.execute(
            "SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly "
            "FROM cookies WHERE host_key LIKE ? OR host_key LIKE ?",
            (f"%{domain}%", f"%.{domain}%"),
        )
        rows = cursor.fetchall()

        if not rows:
            print(f"未找到 {domain} 的 Cookie，请先在浏览器登录B站")
            return False

        with open(output, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# Extracted from browser by Bili Video Summarizer\n\n")
            for host, name, value, path, expires, secure, httponly in rows:
                secure_flag = "TRUE" if secure else "FALSE"
                expires_val = str(expires) if expires else "0"
                f.write(
                    f"{host}\tTRUE\t{path}\t{secure_flag}\t{expires_val}\t{name}\t{value}\n"
                )

        conn.close()
        print(f"成功导出 {len(rows)} 个 Cookie → {output}")
        return True

    except Exception as e:
        print(f"导出失败: {e}")
        print("（Cookie 可能被加密，这是正常的）")
        return False
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def manual_export_guide():
    """显示手动导出指南"""
    print("""
========================================
  Cookie 导出指南（如果自动导出失败）
========================================

方法一：浏览器扩展
  1. 打开 Edge，访问 edge://extensions
  2. 左侧开启"开发人员模式"
  3. 搜索安装 "Cookie-Editor" 或 "Export Cookies"
  4. 打开 bilibili.com → 点扩展 → Export → 保存为 cookies.txt

方法二：开发者工具
  1. 打开 bilibili.com 并登录
  2. 按 F12 → Application（应用程序）
  3. 左侧 Storage → Cookies → https://www.bilibili.com
  4. 全选所有 Cookie（Ctrl+A）→ 复制
  5. 粘贴到记事本，保存为 cookies.txt

========================================
""")


if __name__ == "__main__":
    print("=" * 40)
    print("  B站 Cookie 导出工具")
    print("=" * 40)
    print()

    success = export_cookies()
    if not success:
        manual_export_guide()
