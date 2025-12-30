from typing import Annotated, List, TypedDict
import operator

class AgentState(TypedDict):
    # 用户输入
    query: str
    kb_id: int
    # 记忆片段 (由各节点填充)
    short_term_context: str
    long_term_memory: str
    graph_context: str
    vector_context: str
    # 最终结果
    answer: str
    # 聊天历史 (自动追加)
    history: Annotated[List[str], operator.add]