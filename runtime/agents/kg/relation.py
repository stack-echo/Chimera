import json
from agents.base import BaseAgent
from core.telemetry.tracing import trace_agent

class RelationAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id="KG_Relation_Expert", prompt_file="kg/relation.yaml")

    @trace_agent(agent_name="KG_Relation_Expert")
    def run(self, text: str, entities: list):
        if not entities:
            return []

        # 提取纯实体名列表，减少 Token 消耗
        entity_names = [e.get("name") for e in entities if isinstance(e, dict) and e.get("name")]

        result = self.ask_llm(input_vars={
            "text": text,
            # 将列表转为 JSON 字符串传入模板
            "entities": json.dumps(entity_names, ensure_ascii=False)
        })

        return result if isinstance(result, list) else []