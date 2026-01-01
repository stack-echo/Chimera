from core.telemetry.tracing import trace_agent

class GraphSkill:
    def __init__(self, nebula_store):
        self.db = nebula_store

    @trace_agent("Skill:Nebula_Search")
    def find_entity_context(self, entity_name: str):
        # 亮点：不仅仅找点，还要找相关的 2 步跳跃关系 (2-hop)
        nql = f"LOOKUP ON Entity WHERE Entity.name == '{entity_name}' YIELD id(vertex) AS vid | " \
              f"GO 1 TO 2 STEPS FROM $-.vid OVER * YIELD DISTINCT properties($$).name, properties(edge).type"

        result = self.db.execute("chimera_kb", nql)
        # 格式化为自然语言 context 供 Agent 使用
        return self._format_result(result)