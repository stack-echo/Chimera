from agents.base import BaseAgent
from core.telemetry.tracing import trace_agent

class NERAgent(BaseAgent):
    def __init__(self):
        # 对应 prompts/kg/ner.yaml
        super().__init__(agent_id="KG_NER_Expert", prompt_file="kg/ner.yaml")

    @trace_agent(agent_name="KG_NER_Expert")
    def run(self, text: str):
        # 1. 调用 LLM
        result = self.ask_llm(input_vars={"text": text})

        # 2. 格式校验 (Prompt 可能返回 {"entities": [...]})
        if isinstance(result, dict) and "entities" in result:
            return result["entities"]
        if isinstance(result, list):
            return result

        return []