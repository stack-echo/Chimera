from core.telemetry.tracing import trace_agent

class MemoryAgent:
    def __init__(self, nebula_store, qdrant_client):
        self.graph = nebula_store
        self.vector = qdrant_client

    @trace_agent("Agent:Memory_Recall")
    def recall(self, query: str):
        # 1. 向量检索：寻找相似的情景摘要
        vector_res = self.vector.search(query)

        # 2. 图检索：寻找 Query 涉及实体的长尾属性
        # 比如用户问“Chimera”，它会去 Nebula 查出其 version, status 等
        graph_res = self.graph.execute(f"LOOKUP ON Entity WHERE Entity.name == '{query}'...")

        # 3. 亮点：在 SigNoz 中，你会看到这两个检索是并行的还是串行的，以及各自召回了什么
        return {
            "episodic": vector_res, # 情景记忆
            "semantic": graph_res   # 语义记忆（知识图谱）
        }