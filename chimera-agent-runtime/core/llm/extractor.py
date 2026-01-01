import json
import logging
import re
import yaml
import os
from .llm import LLMClient
from jinja2 import Template

logger = logging.getLogger(__name__)

class KGExtractor:
    def __init__(self):
        self.llm = LLMClient()
        self._load_prompt()

    def _load_prompt(self):
        # 加载 yaml
        path = os.path.join(os.getcwd(), "prompts", "kg", "extraction.yaml")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def extract(self, text: str) -> list:
        """
        输入文本，输出三元组列表
        """
        if len(text) < 50:
            return []

        # 1. 渲染 Prompt
        sys_tmpl = Template(self.config["system"])
        user_tmpl = Template(self.config["user"])

        sys_prompt = sys_tmpl.render()
        user_prompt = user_tmpl.render(text_chunk=text)

        # 2. 调用 LLM (非流式，直接拿结果)
        # 我们需要在 LLMClient 增加一个非流式方法 ask()，或者用 stream 拼凑
        # 这里假设 LLMClient 有一个 ask 方法，或者我们手动调用 client
        try:
            # 临时直接调用 openai client，后续建议封装进 LLMClient.ask()
            response = self.llm.client.chat.completions.create(
                model=self.llm.model_name,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1, # 低温度保证格式稳定
                response_format={"type": "json_object"} # 如果模型支持 JSON 模式最好
            )
            content = response.choices[0].message.content
            return self._parse_json(content)

        except Exception as e:
            logger.error(f"KG Extraction Failed: {e}")
            return []

    def _parse_json(self, text: str):
        """鲁棒的 JSON 解析"""
        try:
            # 1. 尝试直接解析
            return json.loads(text)
        except:
            # 2. 尝试提取 ```json ... ```
            match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    pass
            # 3. 尝试提取 [ ... ]
            match = re.search(r"(\[.*\])", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    pass

            logger.warning(f"无法解析 JSON: {text[:100]}...")
            return []