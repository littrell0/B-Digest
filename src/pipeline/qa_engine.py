"""
AI 问答引擎 — 基于视频逐字稿回答问题
"""
import logging
from typing import Callable, Optional

from openai import OpenAI

from src.config import Config

logger = logging.getLogger("bili_summarizer")

QA_SYSTEM_PROMPT = """你是一个视频内容问答助手。用户会给你一段视频的文字内容，然后问关于视频内容的问题。

请根据视频内容回答问题。规则：
1. 只根据视频内容回答，不要编造信息
2. 如果视频中没有提到，说"这部分内容视频中没有涉及"
3. 以第一人称直接讲述，不要用"视频中提到"、"根据视频"、"作者说"等转述口吻。你就是内容的讲述者。
4. 使用中文回答，保持简洁
5. 不要使用 Markdown 格式（不要用 ** # - 等符号），用纯文本回复"""


class QAEngine:
    """视频内容问答引擎"""

    def __init__(self, config: Config):
        self.config = config
        self._client = None
        self._history = []  # 对话历史

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base_url,
            )
        return self._client

    def reset(self):
        """重置对话历史"""
        self._history = []

    def ask(
        self,
        question: str,
        transcript: str,
        video_title: str = "",
    ) -> str:
        """
        根据逐字稿回答用户问题

        Args:
            question: 用户问题
            transcript: 视频逐字稿
            video_title: 视频标题

        Returns:
            AI 回答
        """
        # 首次提问时加载上下文
        if not self._history:
            context = f"视频标题：{video_title}\n\n视频文字内容：\n\n{transcript}"
            self._history = [
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {"role": "user", "content": f"以下是「{video_title}」的完整内容，请先了解，我会提问。\n\n{context}"},
                {"role": "assistant", "content": f"好的，我已了解「{video_title}」的内容，请问吧。"},
            ]

        # 追加用户问题
        self._history.append({"role": "user", "content": question})

        # 调用 API
        try:
            response = self.client.chat.completions.create(
                model=self.config.api_model,
                messages=self._history,
                max_tokens=2048,
                temperature=0.3,
                stream=False,
            )
            answer = response.choices[0].message.content
            self._history.append({"role": "assistant", "content": answer})
            return answer

        except Exception as e:
            logger.error("问答 API 调用失败: %s", e)
            error_msg = f"API 调用失败: {e}"
            self._history.append({"role": "assistant", "content": error_msg})
            return error_msg

    def ask_stream(
        self,
        question: str,
        transcript: str,
        video_title: str = "",
        callback: Optional[Callable] = None,
    ) -> str:
        """流式问答"""
        # 首次加载上下文
        if not self._history:
            context = f"视频标题：{video_title}\n\n视频文字内容：\n\n{transcript}"
            self._history = [
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {"role": "user", "content": f"以下是「{video_title}」的完整内容，请先了解，我会提问。\n\n{context}"},
                {"role": "assistant", "content": f"好的，我已了解「{video_title}」的内容，请问吧。"},
            ]

        self._history.append({"role": "user", "content": question})

        try:
            stream = self.client.chat.completions.create(
                model=self.config.api_model,
                messages=self._history,
                max_tokens=2048,
                temperature=0.3,
                stream=True,
            )

            full_answer = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_answer += text
                    if callback:
                        callback(text)

            self._history.append({"role": "assistant", "content": full_answer})
            return full_answer

        except Exception as e:
            logger.error("流式问答失败: %s", e)
            return f"API 调用失败: {e}"
