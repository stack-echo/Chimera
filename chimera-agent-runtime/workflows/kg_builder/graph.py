import logging
import uuid
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

# 引入我们刚写的组件
from core.stores.graph_store import NebulaStore
from agents.kg.ner import NERAgent
from agents.kg.relation import RelationAgent
from agents.kg.resolution import ResolutionAgent

logger = logging.getLogger(__name__)

# --- 1. 定义工作流状态 ---
class KGState(TypedDict):
    # 输入
    text: str
    chunk_meta: Dict
    chunk_id: str

    # 中间产物
    entities: List[Dict]   # [{"name": "DeepSeek", "type": "Org"}]
    relations: List[Dict]  # [{"src": "DeepSeek", "dst": "V3", "relation": "released"}]

    # 最终产物 (经过清洗)
    final_graph: Dict      # {"entities": [...], "relations": [...]}

# --- 2. 工作流类 ---
class MultiAgentKGBuilder:
    def __init__(self, nebula: NebulaStore):
        self.nebula = nebula

        # 初始化三个专家 Agent
        self.ner_agent = NERAgent()
        self.re_agent = RelationAgent()
        self.cleaner_agent = ResolutionAgent()

        # 编译图
        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(KGState)

        # 添加节点
        workflow.add_node("ner_node", self.node_ner)
        workflow.add_node("relation_node", self.node_relation)
        workflow.add_node("resolution_node", self.node_resolution)
        workflow.add_node("storage_node", self.node_persist)

        # 定义边 (线性流水线)
        workflow.set_entry_point("ner_node")
        workflow.add_edge("ner_node", "relation_node")
        workflow.add_edge("relation_node", "resolution_node")
        workflow.add_edge("resolution_node", "storage_node")
        workflow.add_edge("storage_node", END)

        return workflow.compile()

    # --- 3. 节点逻辑 (Node Functions) ---

    def node_ner(self, state: KGState):
        """步骤 1: 实体识别"""
        logger.info("🕵️ [KG-1] NER Agent 正在扫描实体...")
        text = state["text"]

        # 调用 Agent
        entities = self.ner_agent.run(text)

        logger.info(f"   -> 发现 {len(entities)} 个候选实体")
        return {"entities": entities}

    def node_relation(self, state: KGState):
        """步骤 2: 关系抽取"""
        logger.info("🔗 [KG-2] Relation Agent 正在分析关系...")
        entities = state.get("entities", [])
        text = state["text"]

        if not entities:
            return {"relations": []}

        # 调用 Agent
        relations = self.re_agent.run(text, entities)

        logger.info(f"   -> 发现 {len(relations)} 条关系")
        return {"relations": relations}

    def node_resolution(self, state: KGState):
        """步骤 3: 实体对齐与清洗"""
        logger.info("⚖️ [KG-3] Resolution Agent 正在清洗图谱...")
        ents = state.get("entities", [])
        rels = state.get("relations", [])

        if not ents:
            return {"final_graph": {"entities": [], "relations": []}}

        # 调用 Agent
        final_graph = self.cleaner_agent.run(ents, rels)
        return {"final_graph": final_graph}

    def node_persist(self, state: KGState):
        """步骤 4: 写入 NebulaGraph"""
        data = state.get("final_graph", {})
        ents = data.get("entities", [])
        rels = data.get("relations", [])

        if not ents and not rels:
            logger.warning("⚠️ [KG-4] 图谱为空，跳过写入")
            return {}

        logger.info(f"💾 [KG-4] 写入图数据库: {len(ents)} 点, {len(rels)} 边")

        # --- A. 转换实体格式 ---
        # NebulaStore 需要: [{"vid": "...", "props": {...}}]
        nebula_ents = []
        # 用 set 去重，防止重复 VID
        seen_vids = set()

        for e in ents:
            name = e.get("name")
            if not name or name in seen_vids: continue

            seen_vids.add(name)
            nebula_ents.append({
                "vid": name, # 使用名字作为 VID (简单策略)
                "props": {
                    "name": name,
                    "type": e.get("type", "Misc"),
                    "desc": e.get("desc", "")
                }
            })

        # --- B. 转换关系格式 ---
        # NebulaStore 需要: [{"src": "...", "dst": "...", "props": {...}}]
        nebula_rels = []
        for r in rels:
            src = r.get("src")
            dst = r.get("dst")
            if not src or not dst: continue

            nebula_rels.append({
                "src": src,
                "dst": dst,
                "props": {
                    "desc": r.get("relation", "related_to"),
                    "weight": 1.0
                }
            })

        # --- C. 执行写入 ---
        try:
            if nebula_ents:
                self.nebula.upsert_entities(nebula_ents)
            if nebula_rels:
                self.nebula.upsert_relations(nebula_rels)

            # 🔥 关键：建立 Chunk -> Entity 的连接 (MENTIONED_IN)
            # 这样以后检索 Chunk 就能找到图，反之亦然
            self.nebula.upsert_chunk_link(
                state["chunk_id"],
                list(seen_vids),
                state["chunk_meta"]
            )
        except Exception as e:
            logger.error(f"❌ Nebula Write Error: {e}", exc_info=True)

        return {}

    # --- 对外接口 ---
    def run(self, chunk_text: str, chunk_meta: dict, chunk_id: str):
        """
        运行流水线 (同步阻塞方式，适合 Worker 调用)
        """
        # 1. 长度检查：太短的文本没必要做图
        if len(chunk_text) < 20:
            return

        initial_state = {
            "text": chunk_text,
            "chunk_meta": chunk_meta,
            "chunk_id": chunk_id,
            "entities": [],
            "relations": [],
            "final_graph": {}
        }

        # Invoke 执行
        self.app.invoke(initial_state)