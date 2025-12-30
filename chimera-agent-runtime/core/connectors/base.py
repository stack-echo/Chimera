from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any
from dataclasses import dataclass

@dataclass
class DocumentChunk:
    content: str
    metadata: Dict[str, Any] # 必须包含 source_id, kb_id, url

class BaseConnector(ABC):
    def __init__(self, kb_id: int, source_id: int, config: dict):
        self.kb_id = kb_id
        self.source_id = source_id
        self.config = config

    @abstractmethod
    def load(self) -> Iterator[DocumentChunk]:
        """
        生成器：流式返回文档切片，避免内存爆炸
        """
        pass