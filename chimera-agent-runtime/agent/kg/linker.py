from agents.base import BaseAgent
from core.telemetry.tracing import trace_agent
from skills.graph_ops import GraphSkill

class LinkerAgent(BaseAgent):
    def __init__(self, nebula_store):
        super().__init__(agent_id="kg_linker", prompt_file="agents/kg_linker.yaml")
        self.graph_skill = GraphSkill(nebula_store)

    @trace_agent("Linker_Expert")
    def run(self, entity_info: dict, context_text: str):
        # 1. 查找图谱中的候选项 (粗排)
        candidates = self.graph_skill.lookup_similar_entities(entity_info['name'])

        # 2. 渲染 Prompt 让 LLM 做决策 (精排/消歧)
        prompt = self.render_prompt(
            entity_name=entity_info['name'],
            entity_type=entity_info['type'],
            context_text=context_text,
            candidates=candidates
        )

        # 3. 获取决策
        decision = self.llm.ask(prompt)
        return decision