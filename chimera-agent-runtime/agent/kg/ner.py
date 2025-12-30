from agents.base import BaseAgent
from core.telemetry.tracing import trace_agent
from core.llm import LLMClient # 假设你封装了 LLM 调用

class NERAgent(BaseAgent):
    def __init__(self):
        # 初始化时加载 YAML 提示词
        super().__init__(agent_id="kg_ner", prompt_file="agents/kg_ner.yaml")
        self.llm = LLMClient()

    @trace_agent("NER_Expert")
    def run(self, text: str):
        # 1. 渲染提示词
        prompt = self.render_prompt(text=text)

        # 2. 调用 LLM (此时 OTel 会自动记录 Span)
        response = self.llm.ask(prompt)

        # 3. 解析结果 (TODO: 增加 Pydantic 校验)
        return response