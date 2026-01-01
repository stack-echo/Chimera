from typing import List
from agents.base import BaseAgent
from core.telemetry.tracing import trace_agent

class QueryAnalysisAgent(BaseAgent):
    def __init__(self):
        # 我们可以复用 kg/ner.yaml 的 Prompt，或者创建一个更通用的
        # 这里暂时复用 ner 的 Prompt，因为它本身就是提取实体的
        super().__init__(agent_id="Query_Analysis_Expert", prompt_file="kg/ner.yaml")

    @trace_agent(agent_name="Query_Analysis_Expert")
    def run(self, query: str) -> List[str]:
        """
        从用户 Query 中提取关键实体名
        """
        # 复用 NER Agent 的 Prompt 逻辑
        result = self.ask_llm(input_vars={"text": query})

        entities = []
        if isinstance(result, dict) and "entities" in result:
            entities = result["entities"]
        elif isinstance(result, list):
            entities = result

        # 提取实体名列表
        entity_names = [e.get("name") for e in entities if isinstance(e, dict) and e.get("name")]

        return entity_names