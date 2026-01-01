import json
from agents.base import BaseAgent
from core.telemetry.tracing import trace_agent

class ResolutionAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id="KG_Resolution_Expert", prompt_file="kg/resolution.yaml")

    @trace_agent(agent_name="KG_Resolution_Expert")
    def run(self, entities: list, relations: list):
        # 构造上下文数据
        graph_data = {
            "entities": entities,
            "relations": relations
        }

        result = self.ask_llm(input_vars={
            "graph_data": json.dumps(graph_data, ensure_ascii=False)
        })

        # 如果 LLM 清洗失败，兜底返回原始数据
        if not result:
            return {"entities": entities, "relations": relations}

        return result