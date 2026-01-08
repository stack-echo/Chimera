import json
import logging
import os
import yaml
from typing import TypedDict, List, Dict, Any, Generator, Optional
from langgraph.graph import StateGraph, END
from jinja2 import Template

# Core & Skills
from core.llm.embedding import EmbeddingModel
from core.llm.llm import LLMClient
from core.stores.qdrant_store import QdrantStore
from skills.reranker import CognitiveReranker
from agents.chat.query_analysis import QueryAnalysisAgent
from core.telemetry.tracing import trace_agent

logger = logging.getLogger(__name__)

# --- 1. 状态定义 ---
class AgentState(TypedDict):
    query: str
    history: List[Any]              # 原始 gRPC Message 对象列表
    query_entities: List[str]       # 提取的实体/关键词
    retrieved_docs: List[Dict]      # 经过 Skyline 过滤后的黄金文档片段
    graph_context: List[str]        # 用于 Prompt 注入的图谱背景描述
    subgraph_data: Dict[str, List]  # 用于前端可视化的点边原始数据
    full_context: str               # 最终拼装的上下文字符串
    answer: str                     # 生成的结果

class ChatWorkflow:
    def __init__(self, nebula: Any, qdrant: QdrantStore, kb_ids: List[int]):
        """
        :param nebula: 企业版 NebulaStore 实例或 None
        :param qdrant: QdrantStore 实例
        :param kb_ids: 知识库 ID 列表
        """
        self.nebula = nebula
        self.qdrant = qdrant
        self.kb_ids = kb_ids

        self.embed_model = EmbeddingModel.get_instance()
        self.llm = LLMClient()
        self.query_analyzer = QueryAnalysisAgent()

        # 加载生成 Prompt
        self.synthesis_prompt_config = self._load_prompt("chat/synthesis.yaml")
        # 构建图
        self.app = self._build_graph()

    def _load_prompt(self, filename):
        """增强的提示词加载逻辑，支持多路径搜索"""
        base_dir = os.getcwd()
        paths = [
            os.path.join(base_dir, "runtime/prompts", filename),
            os.path.join(base_dir, "prompts", filename),
            os.path.join("/app/prompts", filename)
        ]
        for path in paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
        raise FileNotFoundError(f"❌ Prompt file {filename} not found.")

    def _build_graph(self):
        """构建 LangGraph 工作流"""
        workflow = StateGraph(AgentState)

        workflow.add_node("query_analysis", self.node_query_analysis)
        workflow.add_node("retrieve", self.node_retrieve)
        workflow.add_node("generate_prep", self.node_generate_prep)

        workflow.set_entry_point("query_analysis")
        workflow.add_edge("query_analysis", "retrieve")
        workflow.add_edge("retrieve", "generate_prep")
        workflow.add_edge("generate_prep", END)

        return workflow.compile()

    # --- 2. 节点逻辑 (Nodes) ---

    @trace_agent("Node:Query_Analysis")
    def node_query_analysis(self, state: AgentState):
        """步骤 1: 提取关键词并进行意图锚定"""
        logger.info(f"🧠 [Chat-1] 分析意图: {state['query']}")
        entities = self.query_analyzer.run(state["query"])
        return {"query_entities": entities}

    @trace_agent("Node:Dual_Retrieval")
    def node_retrieve(self, state: AgentState):
        """步骤 2: 双螺旋检索 + 多维 Skyline 过滤"""
        query = state["query"]
        entities = state.get("query_entities", [])

        # 2.1 初始化容器
        graph_context = []
        graph_chunk_hits = {}
        subgraph_raw = {"nodes": [], "edges": []}

        # 2.2 企业版图谱支流 (Enterprise)
        if self.nebula:
            try:
                # Stage-1: 获取图谱背景文本 (Cog-RAG)
                graph_context = self.nebula.retrieve_topic_context(entities)
                # 获取图谱评分 (用于 Skyline 过滤)
                graph_chunk_hits = self.nebula.get_chunk_scores_by_entities(entities)
                # 任务 4.1: 获取可视化原始点边
                subgraph_raw = self.nebula.get_subgraph_raw(entities)
                logger.info(f"🕸️ [Chat-2] 图谱命中了 {len(graph_context)} 个背景事实")
            except Exception as e:
                logger.error(f"⚠️ Nebula Retrieval Error: {e}")

        # 2.3 开源版向量支流 (Core)
        query_vec = self.embed_model.encode(query)
        # 召回候选集 (Top-25)，供 Skyline 算法精选
        raw_vector_hits = self.qdrant.search(query_vec, self.kb_ids, top_k=25)

        # 2.4 多维 Skyline 过滤 (Task 3.3)
        refined_docs = CognitiveReranker.skyline_filter(
            vector_results=raw_vector_hits,
            graph_scores=graph_chunk_hits,
            top_k=7
        )

        return {
            "retrieved_docs": refined_docs,
            "graph_context": graph_context,
            "subgraph_data": subgraph_raw
        }

    @trace_agent("Node:Context_Fusion")
    def node_generate_prep(self, state: AgentState):
        """步骤 3: 认知融合上下文拼装"""
        vec_docs = state.get("retrieved_docs", [])
        graph_data = state.get("graph_context", [])

        # A. 格式化图谱事实
        kg_section = ""
        if graph_data:
            kg_section = "【知识图谱背景信息（核心事实）】:\n" + "\n".join([f"- {t}" for t in graph_data])

        # B. 格式化文档片段 (包含 Breadcrumb 层次信息)
        doc_parts = []
        for i, d in enumerate(vec_docs):
            content = d.get('content', '')
            # 这里的 content 已经经过 1.2 任务的 DoclingParser 处理，包含了章节路径
            source = d.get('metadata', {}).get('file_name', '未知文档')
            page = d.get('metadata', {}).get('page_number', '?')
            doc_parts.append(f"证据[{i+1}] (来源: {source}, 页码: {page})\n{content}")

        doc_section = "【相关文档详情（补充细节）】:\n" + "\n\n".join(doc_parts)

        # 拼装最终给 LLM 的上下文
        full_context = f"{kg_section}\n\n{doc_section}".strip()
        if not full_context:
            full_context = "知识库中未找到相关信息。"

        return {"full_context": full_context}

    # --- 3. 运行逻辑 (Stream Handling) ---

    def run_stream(self, initial_state: dict) -> Generator[Dict[str, Any], None, None]:
        """
        执行工作流并产生标准化事件流
        """
        # 1. 执行图逻辑（同步调用，直到 generate_prep 结束）
        final_state = self.app.invoke(initial_state)

        # 2. 推送中间思考过程（ thought ）给前端
        if final_state.get("query_entities"):
            yield {
                "type": "thought",
                "node": "QueryAnalysis",
                "content": f"正在检索实体: {', '.join(final_state['query_entities'])}"
            }

        # 3. 推送任务 4.1 子图数据 (用于 ECharts 绘图)
        if final_state.get("subgraph_data") and final_state["subgraph_data"].get("nodes"):
            yield {
                "type": "subgraph",
                "payload": json.dumps(final_state["subgraph_data"], ensure_ascii=False)
            }

        # 4. 推送参考引用 (reference)
        if final_state.get("retrieved_docs"):
            yield {
                "type": "reference",
                "docs": final_state["retrieved_docs"]
            }

        # 5. 调用 LLM 进行最终生成 (LLM Stream)
        sys_tmpl = self.synthesis_prompt_config.get("system", "")
        user_tmpl = self.synthesis_prompt_config.get("user", "")

        # 注入由 generate_prep 准备好的上下文
        system_prompt = Template(sys_tmpl).render(full_context=final_state["full_context"])
        user_prompt_content = Template(user_tmpl).render(query=final_state["query"])

        try:
            for event in self.llm.stream_chat(
                    query=user_prompt_content,
                    system_prompt=system_prompt,
                    history=initial_state.get("history", []) # 透传历史记录
            ):
                if event["type"] == "content":
                    yield {"type": "delta", "content": event["data"]}
                elif event["type"] == "usage":
                    yield {"type": "usage", "usage": event["data"]}
        except Exception as e:
            logger.error(f"❌ LLM Generation Failed: {e}")
            yield {"type": "error", "content": str(e)}