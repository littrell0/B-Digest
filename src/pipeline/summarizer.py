"""
AI 概述生成模块 - 通过 DeepSeek API 对视频逐字稿进行智能总结
"""
import logging
import time
from typing import Callable, List, Optional

from openai import OpenAI

from src.config import Config
from src.utils.text_utils import split_text_into_chunks, estimate_token_count

logger = logging.getLogger("bili_summarizer")

# 概览详细程度配置
SUMMARY_DETAIL_CONFIG = {
    "精细概览": {
        "ratio": "25%-35%",
        "desc": "完整要点和关键细节",
        "max_chars": None,  # 无上限
    },
    "大致概览": {
        "ratio": "10%-15%",
        "desc": "提炼关键要点并简要说明",
        "max_chars": None,
    },
    "极简概览": {
        "ratio": "≤5%",
        "desc": "仅保留核心结论",
        "max_chars": 200,
    },
}


def _build_summary_prompt(transcript: str, video_title: str, detail: str) -> dict:
    """根据详细程度构建 prompt"""
    config = SUMMARY_DETAIL_CONFIG.get(detail, SUMMARY_DETAIL_CONFIG["大致概览"])
    text_len = len(transcript)

    # 计算目标字数范围
    ratio_str = config["ratio"]
    if detail == "精细概览":
        min_chars = int(text_len * 0.25)
        max_chars = int(text_len * 0.35)
        target = f"{min_chars}-{max_chars}字"
    elif detail == "大致概览":
        min_chars = int(text_len * 0.10)
        max_chars = int(text_len * 0.15)
        target = f"{min_chars}-{max_chars}字"
    else:  # 极简概览
        max_chars = min(200, int(text_len * 0.05))
        target = f"不超过{max_chars}字"

    system = f"""你是一个专业的视频内容概述助手。你的任务是对视频逐字稿进行总结和提炼。

概述详细程度：{detail}
目标字数：{target}（原文 {text_len} 字的 {ratio_str}）""".strip()

    if detail == "精细概览":
        system += f"""

请按以下结构输出概述（使用 Markdown 格式）：

## 视频主题
一句话概括。

## 关键要点
- 列出 5-10 个要点，每个附带简要说明
- 保留关键数据、论据和结论

## 详细内容
分段总结，保留重要细节和论证过程。

## 总结
3-5 句话总结核心内容。

要求：使用中文、忠于原文、不添加原文没有的信息。总字数控制在 {target}。"""
    elif detail == "大致概览":
        system += f"""

请按以下结构输出（使用 Markdown 格式）：

## 视频主题
一句话概括。

## 关键要点
- 列出 3-6 个要点，简要说明

## 总结
2-3 句话总结核心内容。

要求：使用中文、忠于原文。总字数控制在 {target}。"""
    else:  # 极简概览
        system += f"""

请用 1-2 段文字极简总结视频核心内容。不设小标题，仅保留最关键结论。
要求：使用中文、字数不超过原文的5%，且上限200字。"""

    user = f"视频标题：{video_title}\n\n视频逐字稿：\n\n{transcript}" if video_title else f"视频逐字稿：\n\n{transcript}"

    return {
        "system": system,
        "user": user,
        "target": target,
    }


def _build_merge_prompt(summaries: List[str], video_title: str, detail: str) -> dict:
    """构建合并 prompt"""
    config = SUMMARY_DETAIL_CONFIG.get(detail, SUMMARY_DETAIL_CONFIG["大致概览"])
    combined = "\n\n---\n\n".join(
        f"## 第 {i+1} 段总结\n\n{s}" for i, s in enumerate(summaries)
    )

    total_len = sum(len(s) for s in summaries)

    if detail == "精细概览":
        target = f"{int(total_len * 0.6)}-{int(total_len * 0.8)}字"
    elif detail == "大致概览":
        target = f"{int(total_len * 0.4)}-{int(total_len * 0.6)}字"
    else:
        target = "不超过200字"

    return {
        "system": _build_summary_prompt("", video_title, detail)["system"],
        "user": f"视频标题：{video_title}\n\n以下是各分段总结，请合并为一个完整概述（目标{target}）：\n\n{combined}",
        "target": target,
    }


class AISummarizer:
    """AI 概述生成器"""

    def __init__(self, config: Config):
        self.config = config
        self._client = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.config.api_key:
                raise ValueError("DeepSeek API Key 未配置，请在设置中配置")
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base_url,
            )
        return self._client

    def test_connection(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception as e:
            logger.error("DeepSeek API 连接测试失败: %s", e)
            return False

    def summarize(
        self,
        transcript: str,
        video_title: str = "",
        detail: str = "大致概览",
        progress_callback: Optional[Callable] = None,
    ) -> str:
        """
        生成视频内容概述

        Args:
            transcript: 视频逐字稿文本
            video_title: 视频标题
            detail: 概览详细程度 (精细概览/大致概览/极简概览)
            progress_callback: 进度回调 (message: str)
        """
        if detail not in SUMMARY_DETAIL_CONFIG:
            detail = "大致概览"

        # AI概述生成中

        # 短文本直接总结
        if len(transcript) <= 40000:
            if progress_callback:
                progress_callback(f"正在生成{detail}...")
            return self._summarize_full(transcript, video_title, detail)

        # 长文本分块处理
        if progress_callback:
            progress_callback(f"文本较长，分块处理 ({detail})...")
        return self._summarize_with_chunking(transcript, video_title, detail, progress_callback)

    def _summarize_full(self, transcript: str, video_title: str, detail: str) -> str:
        prompt = _build_summary_prompt(transcript, video_title, detail)
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ]
        return self._call_api_with_retry(messages)

    def _summarize_with_chunking(
        self,
        transcript: str,
        video_title: str,
        detail: str,
        progress_callback: Optional[Callable] = None,
    ) -> str:
        chunks = split_text_into_chunks(transcript, max_chars=30000)
        total = len(chunks)
        # 分块处理

        # 阶段1: 逐块总结
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(f"总结第 {i+1}/{total} 段...")
            prompt = _build_summary_prompt(chunk, video_title, detail)
            messages = [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ]
            s = self._call_api_with_retry(messages)
            chunk_summaries.append(s)

        # 阶段2: 合并
        if progress_callback:
            progress_callback("合并分段总结...")
        merge = _build_merge_prompt(chunk_summaries, video_title, detail)
        messages = [
            {"role": "system", "content": merge["system"]},
            {"role": "user", "content": merge["user"]},
        ]
        final = self._call_api_with_retry(messages, max_tokens=4096)
        # 概述合并完成
        return final

    def _call_api_with_retry(
        self,
        messages: list,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        max_retries: int = 3,
    ) -> str:
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.api_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False,
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                logger.warning("API 调用失败 (%d/%d): %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt + 1)
        raise RuntimeError(f"DeepSeek API 调用失败（已重试 {max_retries} 次）: {last_error}")
