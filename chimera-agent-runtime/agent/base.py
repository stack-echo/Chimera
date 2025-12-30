import os
import yaml
from jinja2 import Template
from core.telemetry.tracing import trace_agent
import json
import re

class BaseAgent:
    def __init__(self, agent_id: str, prompt_file: str):
        self.agent_id = agent_id
        # 约定：所有提示词都在项目根目录下的 prompts/ 文件夹
        self.prompt_path = os.path.join("prompts", prompt_file)
        self.config = self._load_config()

    def _load_config(self):
        """从 YAML 加载 Agent 配置和提示词模板"""
        if not os.path.exists(self.prompt_path):
            raise FileNotFoundError(f"未找到提示词文件: {self.prompt_path}")
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def render_prompt(self, **kwargs):
        """使用 Jinja2 渲染动态提示词"""
        template_str = self.config.get("template", "")
        return Template(template_str).render(**kwargs)

    @trace_agent(agent_name="BaseAgent")
    def run(self, state: dict):
        raise NotImplementedError("子类必须实现 run 方法")

    def parse_json_safely(text: str):
        """
        亮点：使用正则提取 JSON 部分，防止 LLM 在 JSON 前后加废话导致程序崩溃
        """
    try:
        # 尝试寻找 [ ] 或 { } 结构
        match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return json.loads(text)
    except Exception as e:
        print(f"❌ JSON 解析失败: {text}")
        return [] # 返回空列表防止下游节点崩溃