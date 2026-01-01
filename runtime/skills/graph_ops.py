from core.telemetry.tracing import trace_agent

class GraphSkill:
    def __init__(self, nebula_store):
        self.db = nebula_store

    @trace_agent("Skill:Graph_Query")
    def get_entity_relations(self, entity_name: str):
        """
        亮点：在图中探测该实体及其周边知识
        """
        # nGQL 语句：查找与该实体相关的 1-2 步关系
        nql = f"""
        MATCH (v:Entity)-[e:RELATION]->(v2)
        WHERE v.Entity.name == '{entity_name}'
        RETURN v.Entity.name, type(e), v2.Entity.name LIMIT 10
        """
        result = self.db.execute(nql)
        return self._format(result)