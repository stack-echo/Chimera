import json
import logging
import os # 🔥 新增引入
import yaml # 🔥 新增引入
from typing import TypedDict, List, Dict, Any, Generator
from langgraph.graph import StateGraph, END
from jinja2 import Template # 🔥 新增引入

from core.llm.embedding import EmbeddingModel
from core.llm.llm import LLMClient
from core.stores.qdrant_store import QdrantStore
from core.stores.graph_store import NebulaStore
# 🔥 引入 QueryAnalysisAgent
from agents.chat.query_analysis import QueryAnalysisAgent

logger = logging.getLogger(__name__)

# --- 状态定义 ---
class AgentState(TypedDict):
    query: str
    chat_history: List[Dict[str, str]]

    query_entities: List[str] # 从 QueryAnalysisAgent 获取

    retrieved_docs: List[Dict]
    graph_context: List[str]   # 图谱结果 (三元组字符串)

    answer: str

class ChatWorkflow:
    def __init__(self, nebula: NebulaStore, qdrant: QdrantStore, kb_ids: List[int]):
        self.nebula = nebula
        self.qdrant = qdrant
        self.kb_ids = kb_ids

        self.embed_model = EmbeddingModel.get_instance()
        self.llm = LLMClient()

        # 🔥 初始化 QueryAnalysisAgent
        self.query_analyzer = QueryAnalysisAgent()

        # 🔥 加载生成 Prompt
        self.synthesis_prompt_config = self._load_prompt("chat/synthesis.yaml")

        self.app = self._build_graph()

    # 🔥 新增：加载 Prompt 的辅助方法
    def _load_prompt(self, filename):
        base_dir = os.getcwd()
        if "chimera-agent-runtime" not in base_dir and os.path.exists("chimera-agent-runtime"):
            base_dir = os.path.join(base_dir, "chimera-agent-runtime")
        path = os.path.join(base_dir, "prompts", filename)

        if not os.path.exists(path):
            raise FileNotFoundError(f"❌ 提示词文件未找到: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        # 定义节点
        workflow.add_node("query_analysis", self.node_query_analysis) # 🔥 新增节点
        workflow.add_node("retrieve", self.node_retrieve)
        workflow.add_node("generate", self.node_generate)

        # 连线
        workflow.set_entry_point("query_analysis") # 🔥 入口改为 Query Analysis
        workflow.add_edge("query_analysis", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    # --- 节点逻辑 ---

    def node_query_analysis(self, state: AgentState):
        """步骤 1: 分析用户 Query，提取关键实体"""
        logger.info(f"🧠 [Chat-1] Query Analysis Agent 正在分析: {state['query']}")
        entities = self.query_analyzer.run(state["query"])
        logger.info(f"   -> 识别到实体: {entities}")
        return {"query_entities": entities}

    def node_retrieve(self, state: AgentState):
        """步骤 2: 双路检索 (Vector + Graph)"""
        query = state["query"]
        entities = state.get("query_entities", []) # 🔥 从上一个节点获取实体

        if not entities: # 如果没有提取到实体，尝试用原始 query 作为兜底
            entities = [query]

        logger.info(f"🔍 [Chat-2] 正在检索: {query} (KB IDs: {self.kb_ids}) with Entities: {entities}")

        # A. 向量检索
        vector_results = []
        try:
            query_vec = self.embed_model.encode(query)
            vector_results = self.qdrant.search(query_vec, self.kb_ids, top_k=3)
        except Exception as e:
            logger.error(f"Vector Search Error: {e}")

        # B. 图谱检索
        graph_triplets = []
        try:
            # 调用 Store，使用提取的实体
            graph_triplets = self.nebula.retrieve_subgraph(entities)
            logger.info(f"🕸️ [Chat-2] 知识图谱命中 {len(graph_triplets)} 条关联知识")

        except Exception as e:
            logger.error(f"Graph Search Error: {e}")

        return {
            "retrieved_docs": vector_results,
            "graph_context": graph_triplets
        }

    def node_generate(self, state: AgentState):
        # 这个节点现在只做状态传递，实际的 Prompt 渲染在 run_stream 统一处理
        return {}

    # --- 核心运行逻辑 ---

    def run_stream(self, initial_state: dict) -> Generator[Dict[str, Any], None, None]:
        # 1. 执行 LangGraph 获取最终状态
        # 我们使用 app.invoke 来同步执行，拿到最终状态
        final_state = self.app.invoke(initial_state)

        # 从最终状态中获取检索结果
        query = final_state["query"]
        vec_docs = final_state.get("retrieved_docs", [])
        graph_triplets = final_state.get("graph_context", [])

        # 2. 组装 Prompt
        doc_context_str = "\n".join([f"- {d['content']}" for d in vec_docs])
        if not doc_context_str:
            doc_context_str = "无相关文档片段。"

        kg_context_str = "\n".join(graph_triplets)
        if not kg_context_str:
            kg_context_str = "无相关知识图谱信息。"

        full_context = f"""
        【文档片段】：
        {doc_context_str}
        
        【知识图谱路径】：
        {kg_context_str}
        """
        # 🔥 从配置文件加载 System 和 User Prompt
        sys_tmpl = self.synthesis_prompt_config.get("system", "")
        user_tmpl = self.synthesis_prompt_config.get("user", "")

        system_prompt = Template(sys_tmpl).render(full_context=full_context)
        user_prompt_content = Template(user_tmpl).render(query=query) # user_prompt 只包含 query

        # 3. 调用 LLM 流式生成
        try:
            for event in self.llm.stream_chat(
                    query=user_prompt_content, # 将渲染后的 user_prompt 内容作为 query 传入
                    system_prompt=system_prompt,
                    history=initial_state.get("history", [])
            ):
                if event["type"] == "content":
                    yield {"type": "delta", "content": event["data"]}
                elif event["type"] == "usage":
                    yield {"type": "usage", "usage": event["data"]}
        except Exception as e:
            logger.error(f"LLM Stream Error in Generation: {e}")
            yield {"type": "error", "content": str(e)}