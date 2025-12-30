from langgraph.graph import StateGraph, END
from workflows.kg_builder.state import KGBuilderState
from agents.kg.ner_agent import NERAgent
from agents.kg.linker_agent import LinkerAgent
from agents.kg.relation_agent import RelationAgent
from skills.graph_ops import GraphSkill
from core.telemetry.tracing import trace_agent

class KGBuildWorkflow:
    def __init__(self, nebula_store):
        # 1. 初始化各路专家
        self.ner_expert = NERAgent()
        self.linker_expert = LinkerAgent(nebula_store)
        self.rel_expert = RelationAgent()
        self.graph_skill = GraphSkill(nebula_store)

        # 2. 构建图
        builder = StateGraph(KGBuilderState)

        # 3. 添加节点
        builder.add_node("ner", self.node_ner)
        builder.add_node("linker", self.node_linker)
        builder.add_node("relation", self.node_relation)
        builder.add_node("storage", self.node_storage)

        # 4. 定义边（严格的线性流水线）
        builder.set_entry_point("ner")
        builder.add_edge("ner", "linker")
        builder.add_edge("linker", "relation")
        builder.add_edge("relation", "storage")
        builder.add_edge("storage", END)

        self.app = builder.compile()

    @trace_agent("Node:NER")
    def node_ner(self, state: KGBuilderState):
        # 实体提取
        entities = self.ner_expert.run(text=state["raw_text"])
        return {"entities": entities}

    @trace_agent("Node:Linker")
    def node_linker(self, state: KGBuilderState):
        # 逐个实体消歧，找到 Nebula 中的 VID
        linked = []
        for ent in state["entities"]:
            res = self.linker_expert.run(ent, state["raw_text"])
            linked.append({**ent, "vid": res.get("decision", "NEW")})
        return {"linked_entities": linked}

    @trace_agent("Node:Relation")
    def node_relation(self, state: KGBuilderState):
        # 建立关系连线
        triples = self.rel_expert.run(state["linked_entities"], state["raw_text"])
        return {"triples": triples}

    @trace_agent("Node:Storage")
    def node_storage(self, state: KGBuilderState):
        # 🔥 亮点：写入 NebulaGraph，完成闭环
        for t in state["triples"]:
            self.graph_skill.upsert_triple(t)
        return {}