import os
import yaml
import json
import re
import logging
from jinja2 import Template
from core.llm.llm import LLMClient
# 假设 trace_agent 在这里，根据你的项目结构调整
from core.telemetry.tracing import trace_agent

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, agent_id: str, prompt_file: str):
        """
        :param agent_id: 智能体唯一标识 (用于日志/监控)
        :param prompt_file: 提示词文件名 (相对 prompts/ 目录)
        """
        self.agent_id = agent_id
        self.llm = LLMClient()

        # 路径处理：兼容本地运行和 Docker
        base_dir = os.getcwd()
        if "chimera-agents-runtime" not in base_dir and os.path.exists("chimera-agents-runtime"):
            base_dir = os.path.join(base_dir, "chimera-agents-runtime")

        self.prompt_path = os.path.join(base_dir, "prompts", prompt_file)
        self.config = self._load_config()

    def _load_config(self):
        """从 YAML 加载 Agent 配置"""
        if not os.path.exists(self.prompt_path):
            raise FileNotFoundError(f"❌ 未找到提示词文件: {self.prompt_path}")
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def render_prompt(self, template_str: str, **kwargs):
        """使用 Jinja2 渲染动态提示词"""
        if not template_str:
            return ""
        return Template(template_str).render(**kwargs)

    def parse_json_safely(self, text: str):
        """
        鲁棒的 JSON 解析器：自动清洗 Markdown 标记
        """
        text = text.strip()
        try:
            # 1. 尝试直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                # 2. 尝试提取 ```json 块
                match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
                if match:
                    return json.loads(match.group(1))

                # 3. 尝试提取 [...] 或 {...}
                match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
                if match:
                    return json.loads(match.group(1))

                raise ValueError("No JSON found")
            except Exception as e:
                logger.warning(f"⚠️ Agent [{self.agent_id}] JSON 解析失败: {text[:50]}... Error: {e}")
                return [] # 默认返回空列表，防止 Crash

    def ask_llm(self, input_vars: dict, response_format="json"):
        """
        通用的 LLM 调用方法
        :param input_vars: 渲染模板所需的变量字典
        """
        # 1. 渲染 System 和 User Prompt
        sys_tmpl = self.config.get("system", "")
        user_tmpl = self.config.get("user", "")

        sys_prompt = self.render_prompt(sys_tmpl, **input_vars)
        user_prompt = self.render_prompt(user_tmpl, **input_vars)

        # 2. 调用 LLM (复用 LLMClient)
        try:
            # 这里我们直接使用 client.chat.completions 以获得非流式结果
            # 如果 LLMClient 封装了 ask() 方法更好，这里假设直接调 client
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

            # 3. 解析结果
            if response_format == "json":
                return self.parse_json_safely(content)
            return content

        except Exception as e:
            logger.error(f"❌ Agent [{self.agent_id}] LLM 调用异常: {e}")
            # 返回空结构以保证流程不中断
            return [] if response_format == "json" else ""

    def run(self, *args, **kwargs):
        raise NotImplementedError("子类必须实现 run 方法")