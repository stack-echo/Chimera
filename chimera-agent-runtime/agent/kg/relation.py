from agents.base import BaseAgent
from core.telemetry.tracing import trace_agent

class RelationAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id="kg_relation", prompt_file="agents/kg_relation.yaml")

    @trace_agent("Relation_Expert")
    def run(self, entities: list, text: str):
        # 渲染提示词：传入之前 NER 识别出的实体名
        prompt = self.render_prompt(
            entities=[e['name'] for e in entities],
            text=text
        )

        # 调用 LLM (此时 SigNoz 会记录下这一步的推理)
        response = self.llm.ask(prompt)
        return response