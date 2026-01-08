import json
import os
import re
from jinja2 import Template
import yaml
import logging
from core.llm.llm import LLMClient

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, agent_id: str, prompt_file: str):
        self.agent_id = agent_id
        self.llm = LLMClient()

        # 路径处理：基于当前文件物理位置，向上寻找 prompts
        current_file_path = os.path.abspath(__file__)
        runtime_root = os.path.dirname(os.path.dirname(current_file_path))

        self.prompt_path = os.getenv("CHIMERA_PROMPTS_PATH")
        if not self.prompt_path:
            self.prompt_path = os.path.join(runtime_root, "prompts", prompt_file)
        else:
            self.prompt_path = os.path.join(self.prompt_path, prompt_file)

        # 4. 容错处理：打印路径（仅在 Debug 模式或报错时，方便排查）
        if not os.path.exists(self.prompt_path):
            logger.error(f"❌ 提示词文件定位失败！")
            logger.error(f"   预期路径: {self.prompt_path}")
            logger.error(f"   当前脚本位置: {current_file_path}")
            logger.error(f"   当前工作目录(CWD): {os.getcwd()}")
            raise FileNotFoundError(f"Prompt file not found at {self.prompt_path}")

        self.config = self._load_config()

    def _load_config(self):
        if not os.path.exists(self.prompt_path):
            raise FileNotFoundError(f"❌ 未找到提示词文件: {self.prompt_path}")
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def render_prompt(self, template_str: str, **kwargs):
        if not template_str: return ""
        return Template(template_str).render(**kwargs)

    def parse_json_safely(self, text: str):
        """鲁棒的 JSON 解析器"""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                # 尝试提取 ```json 块
                match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
                if match: return json.loads(match.group(1))
                # 尝试提取 [...] 或 {...}
                match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
                if match: return json.loads(match.group(1))
                raise ValueError("No JSON found")
            except Exception as e:
                logger.warning(f"⚠️ Agent [{self.agent_id}] JSON 解析失败: {e}")
                return []

    def ask_llm(self, input_vars: dict, response_format="json"):
        """通用的 LLM 调用方法"""
        sys_tmpl = self.config.get("system", "")
        user_tmpl = self.config.get("user", "")

        sys_prompt = self.render_prompt(sys_tmpl, **input_vars)
        user_prompt = self.render_prompt(user_tmpl, **input_vars)

        try:
            # 这里的 client 是 openai 风格的 client
            response = self.llm.client.chat.completions.create(
                model=self.llm.model_name,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"} if response_format == "json" else None
            )
            content = response.choices[0].message.content

            if response_format == "json":
                return self.parse_json_safely(content)
            return content

        except Exception as e:
            logger.error(f"❌ Agent [{self.agent_id}] LLM 调用异常: {e}")
            return [] if response_format == "json" else ""