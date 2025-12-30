from typing import List, TypedDict, Optional

class KGBuilderState(TypedDict):
    # 输入的原始文本内容
    raw_text: str
    # 抽取出的初步实体列表
    entities: List[dict]
    # 经过消歧/链接后的实体 (带有 Nebula VID)
    linked_entities: List[dict]
    # 提取出的三元组关系
    triples: List[dict]
    # 错误信息记录
    error: Optional[str]