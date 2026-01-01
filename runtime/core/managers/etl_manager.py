import json
import time
import uuid
import logging
import traceback
from typing import Generator, Dict, Any, Optional

from core.llm.embedding import EmbeddingModel
from core.stores.qdrant_store import QdrantStore
from core.connectors.base import ConnectorFactory

logger = logging.getLogger(__name__)

class ETLManager:
    def __init__(self, qdrant_store: QdrantStore, nebula_store: Any = None):
        """
        初始化 ETL 管理器
        :param qdrant_store: 向量数据库实例 (必须)
        :param nebula_store: 图数据库实例 (可选，如果为 None 则不构建图谱)
        """
        self.qdrant = qdrant_store
        self.nebula = nebula_store
        self.embed_model = EmbeddingModel.get_instance()

        # 🔥 动态初始化 KG Builder (企业版功能)
        self.kg_builder = None
        if self.nebula:
            try:
                # 尝试导入 KG Builder
                # 注意：在 Phase 3 物理拆分后，这个路径可能会变，或者通过 enterprise_loader 注册
                # 这里暂时保持原有路径，但加上 try-except 以防文件被移走
                from workflows.kg_builder.graph import MultiAgentKGBuilder
                self.kg_builder = MultiAgentKGBuilder(self.nebula)
                logger.info("🧠 [ETL] Knowledge Graph Builder activated.")
            except ImportError:
                logger.warning("⚠️ [ETL] Enterprise KG Builder module not found.")
            except Exception as e:
                logger.error(f"❌ [ETL] KG Builder init failed: {e}")

    def sync_datasource(self, kb_id: int, source_id: int, source_type: str, config_json: str) -> Generator[Dict[str, Any], None, None]:
        """
        执行数据源同步任务 (生成器)
        :yield: 进度信息 {"chunks": int, "pages": int}
        """
        start_time = time.time()
        logger.info(f"🔄 [ETL Start] KB={kb_id} Source={source_id} Type={source_type}")

        try:
            config = json.loads(config_json)

            # 1. 获取连接器
            connector_cls = ConnectorFactory.get_connector(source_type)
            if not connector_cls:
                raise ValueError(f"Unsupported/Missing connector type: '{source_type}'. Please check Enterprise License.")

            connector = connector_cls(kb_id, source_id, config)

            chunks_buffer = []
            total_chunks = 0

            # 2. 遍历文档切片
            for chunk in connector.load():
                # 生成全局唯一 ID
                chunk_uuid = str(uuid.uuid4())

                # 向量化
                vector = self.embed_model.encode(chunk.content)

                # 准备 Qdrant Payload
                payload = {
                    "content": chunk.content,
                    "kb_id": kb_id,
                    "source_id": source_id,
                    **chunk.metadata
                }

                chunks_buffer.append({
                    "id": chunk_uuid,
                    "vector": vector,
                    "payload": payload
                })

                # 3. 触发图谱构建 (如果启用了)
                if self.kg_builder:
                    try:
                        # 这是一个耗时操作，目前同步执行
                        self.kg_builder.run(chunk.content, chunk.metadata, chunk_uuid)
                    except Exception as kg_e:
                        logger.warning(f"⚠️ KG Build failed for chunk {chunk_uuid}: {kg_e}")

                # 4. 批处理写入向量库 (每 50 条)
                if len(chunks_buffer) >= 50:
                    self.qdrant.upsert_chunks(chunks_buffer)
                    total_chunks += len(chunks_buffer)
                    chunks_buffer = []
                    # 实时汇报进度 (可选)
                    # yield {"chunks": total_chunks}

            # 写入剩余 buffer
            if chunks_buffer:
                self.qdrant.upsert_chunks(chunks_buffer)
                total_chunks += len(chunks_buffer)

            duration = time.time() - start_time
            logger.info(f"✅ [ETL Done] Chunks={total_chunks} Time={duration:.2f}s")

            # 返回最终统计
            yield {
                "success": True,
                "chunks": total_chunks,
                "pages": 0  # 如果 connector 能提供总页数更好
            }

        except Exception as e:
            logger.error(f"❌ [ETL Error] {str(e)}")
            logger.error(traceback.format_exc())
            raise e  # 抛出异常由 Service 层捕获封装 gRPC 错误