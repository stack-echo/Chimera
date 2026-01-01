import json
import logging
import os
import yaml
from typing import TypedDict, List, Dict, Any, Generator, Optional
from langgraph.graph import StateGraph, END
from jinja2 import Template

from core.llm.embedding import EmbeddingModel
from core.llm.llm import LLMClient
from core.stores.qdrant_store import QdrantStore
# ❌ 已删除: from core.stores.graph_store import NebulaStore (这是企业版组件，不能在 Core 直接引入)
from agents.chat.query_analysis import QueryAnalysisAgent

logger = logging.getLogger(__name__)

# --- 状态定义 ---
class AgentState(TypedDict):
    query: str
    chat_history: List[Dict[str, str]]
    query_entities: List[str]
    retrieved_docs: List[Dict]
    graph_context: List[str]
    answer: str

class ChatWorkflow:
    # 🔥 修改点：nebula 类型改为 Any，允许传入 None
    def __init__(self, nebula: Any, qdrant: QdrantStore, kb_ids: List[int]):
        self.nebula = nebula
        self.qdrant = qdrant
        self.kb_ids = kb_ids

        self.embed_model = EmbeddingModel.get_instance()
        self.llm = LLMClient()
        self.query_analyzer = QueryAnalysisAgent()

        # 加载生成 Prompt
        self.synthesis_prompt_config = self._load_prompt("chat/synthesis.yaml")
        self.app = self._build_graph()

    def _load_prompt(self, filename):
        base_dir = os.getcwd()
        # 兼容不同启动路径
        if "runtime" not in base_dir and os.path.exists("runtime"):
            base_dir = os.path.join(base_dir, "runtime")

        # 假设 prompts 目录在 runtime/prompts
        path = os.path.join(base_dir, "prompts", filename)

        if not os.path.exists(path):
            # 回退尝试 (处理 Docker 路径可能不同)
            path = os.path.join("/app/prompts", filename)

        if not os.path.exists(path):
            # 再次回退，防止本地调试路径问题
            if os.path.exists(f"prompts/{filename}"):
                path = f"prompts/{filename}"
            else:
                # 最后的兜底，如果是 runtimeservice 启动
                path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts", filename)

        if not os.path.exists(path):
            raise FileNotFoundError(f"❌ 提示词文件未找到: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("query_analysis", self.node_query_analysis)
        workflow.add_node("retrieve", self.node_retrieve)
        workflow.add_node("generate", self.node_generate)

        workflow.set_entry_point("query_analysis")
        workflow.add_edge("query_analysis", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    # --- 节点逻辑 ---

    def node_query_analysis(self, state: AgentState):
        """步骤 1: 分析用户 Query，提取关键实体"""
        logger.info(f"🧠 [Chat-1] Query Analysis: {state['query']}")
        entities = self.query_analyzer.run(state["query"])
        return {"query_entities": entities}

    def node_retrieve(self, state: AgentState):
        """步骤 2: 双路检索 (Vector + Graph)"""
        query = state["query"]
        entities = state.get("query_entities", [])
        if not entities: entities = [query]

        # A. 向量检索 (Core)
        vector_results = []
        try:
            query_vec = self.embed_model.encode(query)
            vector_results = self.qdrant.search(query_vec, self.kb_ids, top_k=3)
        except Exception as e:
            logger.error(f"Vector Search Error: {e}")

        # B. 图谱检索 (Enterprise)
        graph_triplets = []
        # 🔥 关键修改：先检查 self.nebula 是否存在
        if self.nebula:
            try:
                # Duck Typing: 只要传入的对象有 retrieve_subgraph 方法就行
                graph_triplets = self.nebula.retrieve_subgraph(entities)
                logger.info(f"🕸️ [Chat-2] KG Hit: {len(graph_triplets)} relations")
            except Exception as e:
                logger.error(f"Graph Search Error: {e}")
        else:
            logger.debug("🕸️ [Chat-2] Skipping KG (Enterprise feature disabled)")

        return {
            "retrieved_docs": vector_results,
            "graph_context": graph_triplets
        }

    def node_generate(self, state: AgentState):
        return {}

    # --- 运行逻辑 ---

    def run_stream(self, initial_state: dict) -> Generator[Dict[str, Any], None, None]:
        final_state = self.app.invoke(initial_state)

        query = final_state["query"]
        vec_docs = final_state.get("retrieved_docs", [])
        graph_triplets = final_state.get("graph_context", [])

        # 组装 Context
        doc_context_str = "\n".join([f"- {d['content']}" for d in vec_docs])
        if not doc_context_str: doc_context_str = "无相关文档片段。"

        kg_context_str = "\n".join(graph_triplets)
        if not kg_context_str: kg_context_str = "无相关知识图谱信息。"

        full_context = f"【文档片段】：\n{doc_context_str}\n\n【知识图谱路径】：\n{kg_context_str}"

        # 渲染 Prompt
        sys_tmpl = self.synthesis_prompt_config.get("system", "")
        user_tmpl = self.synthesis_prompt_config.get("user", "")

        system_prompt = Template(sys_tmpl).render(full_context=full_context)
        user_prompt_content = Template(user_tmpl).render(query=query)

        # 流式生成
        try:
            for event in self.llm.stream_chat(
                    query=user_prompt_content,
                    system_prompt=system_prompt,
                    history=initial_state.get("history", [])
            ):
                if event["type"] == "content":
                    yield {"type": "delta", "content": event["data"]}
                elif event["type"] == "usage":
                    yield {"type": "usage", "usage": event["data"]}
        except Exception as e:
            logger.error(f"LLM Generation Error: {e}")
            yield {"type": "error", "content": str(e)}