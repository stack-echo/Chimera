from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, Type, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class DocumentChunk:
    content: str
    metadata: Dict[str, Any]  # 必须包含 source_id, kb_id

class BaseConnector(ABC):
    """
    所有数据源连接器的基类 (Core & Enterprise)
    """
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

# 🔥 核心重构：连接器工厂
class ConnectorFactory:
    _registry: Dict[str, Type[BaseConnector]] = {}

    @classmethod
    def register(cls, type_name: str, connector_cls: Type[BaseConnector]):
        """
        插件注册入口。
        例如: ConnectorFactory.register("feishu", FeishuConnector)
        """
        if type_name in cls._registry:
            logger.warning(f"🔌 Connector '{type_name}' is being overwritten by {connector_cls.__name__}")
        else:
            logger.info(f"🔌 Connector registered: '{type_name}' -> {connector_cls.__name__}")

        cls._registry[type_name] = connector_cls

    @classmethod
    def get_connector(cls, type_name: str) -> Optional[Type[BaseConnector]]:
        """
        获取连接器类。如果未注册（如企业版未加载），返回 None
        """
        return cls._registry.get(type_name)

    @classmethod
    def list_available(cls):
        return list(cls._registry.keys())