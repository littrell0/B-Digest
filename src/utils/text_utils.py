"""
文本处理工具模块
"""
import re
from typing import List


def parse_vtt_to_text(vtt_content: str) -> str:
    """
    将 WebVTT 字幕内容解析为纯文本

    处理步骤:
    1. 移除 WEBVTT 头部
    2. 移除时间戳行 (00:00:01.000 --> 00:00:03.000)
    3. 移除字幕序号
    4. 移除 VTT 标签 (如 <c.bg_transparent> 等)
    5. 合并重复/分段行
    6. 输出连续纯文本

    Args:
        vtt_content: VTT 格式的字幕原始文本

    Returns:
        清理后的纯文本字幕
    """
    lines = vtt_content.split("\n")
    result: List[str] = []
    i = 0

    # 跳过 WEBVTT 头部
    while i < len(lines) and (
        lines[i].strip().startswith("WEBVTT")
        or lines[i].strip().startswith("Kind:")
        or lines[i].strip().startswith("Language:")
        or lines[i].strip() == ""
    ):
        i += 1

    while i < len(lines):
        line = lines[i].strip()

        # 跳过空行
        if not line:
            i += 1
            continue

        # 跳过时间戳行 (格式: 00:00:01.000 --> 00:00:03.000)
        if re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}", line):
            i += 1
            continue

        # 跳过硬编码的定位行 (如 "align:start position:0%")
        if line.startswith("align:") or line.startswith("position:"):
            i += 1
            continue

        # 跳过纯数字序号
        if line.isdigit():
            i += 1
            continue

        # 移除 VTT 标签 (如 <c.bg_transparent>, </c>, <00:00:01.000> 等)
        text = re.sub(r"<[^>]+>", "", line)
        text = text.strip()

        if text:
            # 去重: 如果和上一行相同则跳过
            if result and result[-1] == text:
                i += 1
                continue
            result.append(text)

        i += 1

    return "\n".join(result)


def parse_srt_to_text(srt_content: str) -> str:
    """
    将 SRT 字幕内容解析为纯文本

    Args:
        srt_content: SRT 格式的字幕原始文本

    Returns:
        清理后的纯文本字幕
    """
    lines = srt_content.split("\n")
    result: List[str] = []

    for line in lines:
        line = line.strip()

        # 跳过空行
        if not line:
            continue

        # 跳过序号
        if line.isdigit():
            continue

        # 跳过时间戳行
        if re.match(r"^\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}", line):
            continue

        # 移除 SRT 标签 (如 <font>, <b>, <i> 等)
        text = re.sub(r"<[^>]+>", "", line)
        text = text.strip()

        if text:
            # 去重
            if result and result[-1] == text:
                continue
            result.append(text)

    return "\n".join(result)


def split_text_into_chunks(text: str, max_chars: int = 80000) -> List[str]:
    """
    将长文本按自然段落分割为多个块，每块不超过 max_chars

    Args:
        text: 要分割的文本
        max_chars: 每块最大字符数

    Returns:
        文本块列表
    """
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    paragraphs = text.split("\n\n")
    current_chunk: List[str] = []
    current_length = 0

    for para in paragraphs:
        para_len = len(para)

        if current_length + para_len > max_chars and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_length = 0

        current_chunk.append(para)
        current_length += para_len

        # 单个段落超过限制，强制拆分
        while current_length > max_chars:
            split_point = max_chars - (current_length - para_len)
            if split_point <= 0:
                split_point = max_chars
            chunks.append(para[:split_point])
            para = para[split_point:]
            para_len = len(para)
            current_length = para_len

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks if chunks else [text]


def estimate_token_count(text: str) -> int:
    """
    粗略估算 token 数量 (中文按每字符1.5 token, 英文按每单词1.3 token)

    Args:
        text: 要估算的文本

    Returns:
        估算的 token 数
    """
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    other_chars = len(text) - chinese_chars - sum(
        len(w) for w in re.findall(r"[a-zA-Z]+", text)
    )

    return int(chinese_chars * 1.5 + english_words * 1.3 + other_chars * 0.5)
