from openai import OpenAI
from config import Config

class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL
        )

    def stream_chat(self, query: str, system_prompt: str = None):
        """流式对话生成"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": query})

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=True
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"[LLM Error] {str(e)}"