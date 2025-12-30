import json
import logging
from typing import TypedDict, List, Dict, Any, Generator
from langgraph.graph import StateGraph, END

from core.llm.embedding import EmbeddingModel
from core.llm.llm import LLMClient
from core.stores.qdrant_store import QdrantStore
from core.stores.graph_store import NebulaStore

logger = logging.getLogger(__name__)

# --- 状态定义 ---
class AgentState(TypedDict):
    query: str
    chat_history: List[Dict[str, str]] # [{"role": "user", "content": "..."}]

    # 上下文
    retrieved_docs: List[Dict]
    graph_context: str

    # 最终答案
    answer: str

class ChatWorkflow:
    def __init__(self, nebula: NebulaStore, qdrant: QdrantStore, kb_ids: List[int]):
        """
        初始化工作流，注入资源
        """
        self.nebula = nebula
        self.qdrant = qdrant
        self.kb_ids = kb_ids

        # 初始化模型
        self.embed_model = EmbeddingModel.get_instance()
        self.llm = LLMClient()

        # 构建图
        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        # 定义节点
        workflow.add_node("retrieve", self.node_retrieve)
        workflow.add_node("generate", self.node_generate)

        # 定义边
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    # --- 节点逻辑 ---

    def node_retrieve(self, state: AgentState):
        """
        检索节点：同时查询 向量库(Qdrant) 和 图数据库(Nebula)
        """
        query = state["query"]
        logger.info(f"🔍 [Retrieve] 正在检索: {query} (KB IDs: {self.kb_ids})")

        # 1. 向量检索 (Qdrant)
        try:
            query_vector = self.embed_model.encode(query)
            # 调用我们刚写的 search 方法，传入 kb_ids 过滤
            vector_results = self.qdrant.search(
                query_vector=query_vector,
                kb_ids=self.kb_ids,
                top_k=5
            )
        except Exception as e:
            logger.error(f"Qdrant Search Error: {e}")
            vector_results = []

        # 2. 图检索 (Nebula) - 简单示例：查找包含关键词的实体
        # (这里为了稳健，如果图没准备好，先 try-catch 掉)
        graph_text = ""
        try:
            # 这里的逻辑可以做得很复杂，比如提取实体 -> 查子图
            # 这里仅作占位，防止报错
            pass
        except Exception as e:
            logger.error(f"Nebula Search Error: {e}")

        return {
            "retrieved_docs": vector_results,
            "graph_context": graph_text
        }

    def node_generate(self, state: AgentState):
        """
        生成节点：组装 Prompt 但不直接调用 LLM。
        这里我们不做实际生成，而是准备好上下文，实际的流式生成在 run_stream 里触发。
        """
        # 仅做状态传递，LangGraph 运行完这个节点后，我们会拿到 state
        return {}

    # --- 核心运行逻辑 ---

    def run_stream(self, initial_state: dict) -> Generator[Dict[str, Any], None, None]:
        """
        执行工作流，并以生成器形式返回事件
        这适配了 runtime_service.py 的调用方式
        """

        # 1. 发送“思考”事件
        yield {
            "type": "thought",
            "node": "Retrieve",
            "content": "正在知识库中检索相关文档...",
            "duration": 0
        }

        # 2. 运行检索节点 (手动 invoke graph 的一部分，或者运行整个 graph 拿到结果)
        # 为了简单，我们这里直接运行 LangGraph，拿到检索结果
        # 注意：这里我们使用 invoke 同步执行检索，因为检索通常很快

        # 构造 LangGraph 需要的输入
        input_state = {
            "query": initial_state["query"],
            "chat_history": initial_state.get("history", []),
            "retrieved_docs": [],
            "graph_context": "",
            "answer": ""
        }

        # 运行图 (直到 retrieve 完成)
        # 这里有一个技巧：我们手动调用节点逻辑，以便更好控制流式输出
        # 或者，我们可以运行 app.invoke(input_state) 拿到 context

        # === 手动执行 Retrieval 阶段 ===
        retrieve_output = self.node_retrieve(input_state)
        docs = retrieve_output["retrieved_docs"]

        # 发送引用事件
        if docs:
            formatted_docs = []
            for doc in docs:
                meta = doc.get("metadata", {})
                formatted_docs.append({
                    "file_name": meta.get("file_name", "unknown"),
                    "page": meta.get("page_number", 1),
                    "score": doc.get("score", 0),
                    "snippet": doc.get("content", "")[:100] + "..."
                })
            yield {
                "type": "reference",
                "docs": formatted_docs
            }

        # === 执行 Generation 阶段 ===
        yield {
            "type": "thought",
            "node": "Generate",
            "content": "正在整理检索结果并生成回答...",
            "duration": 0
        }

        # 3. 组装 Prompt
        context_str = "\n\n".join([f"[文档片段]: {d['content']}" for d in docs])
        if not context_str:
            context_str = "未找到相关文档，请根据常识回答。"

        system_prompt = f"""
你是一个专业的企业知识助手。请根据以下参考资料回答用户问题。
如果参考资料无法回答问题，请诚实说明。

【参考资料】：
{context_str}
"""
        # Query 独立传递
        # 在 llm.stream_chat 中会处理 messages

        # 4. 调用 LLM 流式生成
        # 这里直接调用 LLMClient，绕过 Graph 的静态返回，实现 Token 流
        try:
            for event in self.llm.stream_chat(
                    query=initial_state['query'],
                    system_prompt=system_prompt,
                    history=initial_state.get("history", [])
            ):
                # 透传内容
                if event["type"] == "content":
                    yield {
                        "type": "delta",
                        "content": event["data"]
                    }
                # 🔥 透传 Usage
                elif event["type"] == "usage":
                    yield {
                        "type": "usage",
                        "usage": event["data"]
                    }
        except Exception as e:
            logger.error(f"LLM Stream Error: {e}")
            yield {
                "type": "delta",
                "content": f"[生成出错: {str(e)}]"
            }