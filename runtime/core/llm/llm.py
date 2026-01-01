from openai import OpenAI
from config import Config
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL
        )
        self.model_name = "deepseek-chat" # 或从 Config 读取

    def stream_chat(self, query: str, system_prompt: str, history: list = None):
        """
        流式对话
        :param history: 格式 [{"role": "user", "content": "..."}]
        """
        messages = []

        # 1. 添加 System Prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 2. 添加历史记录 (限制最近 5 轮，防止 Token 溢出)
        if history:
            # 简单的转换逻辑，确保格式正确
            for msg in history[-10:]:
                # 兼容 proto 的 Message 对象或 dict
                role = getattr(msg, 'role', None) or msg.get('role')
                content = getattr(msg, 'content', None) or msg.get('content')
                if role and content:
                    messages.append({"role": role, "content": content})

        # 3. 添加当前问题 (如果 query 已经在 prompts 里了，这里可以不加，取决于 prompts 策略)
        messages.append({"role": "user", "content": query})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True,
                temperature=0.3,
                stream_options={"include_usage": True},
            )

            for chunk in response:
                # 1. 处理内容增量
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {
                        "type": "content",
                        "data": chunk.choices[0].delta.content
                    }
                # 2. 🔥 处理 Token 统计 (通常在最后一块)
                if hasattr(chunk, 'usage') and chunk.usage:
                    yield {
                        "type": "usage",
                        "data": {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens
                        }
                    }

        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            raise e