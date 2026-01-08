import json
import time
import uuid
import logging
import traceback
from typing import Generator, Dict, Any, Optional

from core.llm.embedding import EmbeddingModel
from core.stores.qdrant_store import QdrantStore
from core.connectors.base import ConnectorFactory
from core.managers.kg_registry import KGRegistry

logger = logging.getLogger(__name__)

class ETLManager:
    def __init__(self, qdrant_store: QdrantStore, nebula_store: Any = None):
        self.qdrant = qdrant_store
        self.nebula = nebula_store
        self.embed_model = EmbeddingModel.get_instance()
        self.is_kg_active = False

        if self.nebula:
            self._init_kg_status()

    def _init_kg_status(self):
        """
        不再需要 try-import，直接检查注册表
        """
        if KGRegistry.is_active():
            self.is_kg_active = True
            logger.info("🔓 [ETL] Enterprise GraphRAG Pipeline linked via Registry.")
        else:
            logger.info("ℹ️ [ETL] KG Agents not registered. Skipping KG construction.")
            self.nebula = None

    def sync_datasource(self, kb_id: int, source_id: int, source_type: str, config_json: str) -> Generator[Dict[str, Any], None, None]:
        """
        执行同步任务：向量入库 + (可选) 图谱入库
        """
        start_time = time.time()
        logger.info(f"🔄 [ETL Start] KB={kb_id} Source={source_id} Type={source_type}")

        try:
            config = json.loads(config_json)
            connector_cls = ConnectorFactory.get_connector(source_type)
            if not connector_cls:
                raise ValueError(f"Unsupported connector: {source_type}")

            connector = connector_cls(kb_id, source_id, config)
            chunks_buffer = []
            total_count = 0

            for chunk in connector.load():
                chunk_uuid = str(uuid.uuid4())
                vector = self.embed_model.encode(chunk.content)

                payload = {
                    "id": chunk_uuid,
                    "vector": vector,
                    "payload": {
                        "content": chunk.content,
                        "kb_id": kb_id,
                        "source_id": source_id,
                        **chunk.metadata
                    }
                }
                chunks_buffer.append(payload)

                # --- 运行图谱流水线 ---
                if self.nebula and self.is_kg_active:
                    self._run_kg_pipeline_safe(chunk, chunk_uuid)

                # --- 批量写入 Qdrant (每 10 条) ---
                if len(chunks_buffer) >= 10:
                    self.qdrant.upsert_chunks(chunks_buffer)
                    total_count += len(chunks_buffer)
                    chunks_buffer = []
                    yield {"chunks": total_count, "status": "syncing"}

            # 写入剩余部分
            if chunks_buffer:
                self.qdrant.upsert_chunks(chunks_buffer)
                total_count += len(chunks_buffer)

            logger.info(f"💾 总计向 Qdrant 写入 {total_count} 条向量数据")
            yield {"success": True, "chunks": total_count}

        except Exception as e:
            logger.error(f"❌ [ETL Error] {str(e)}")
            logger.error(traceback.format_exc())
            raise e

    def _run_kg_pipeline_safe(self, chunk, chunk_id: str):
        """
        执行流水线时，直接从注册表取 Agent
        """
        if not self.nebula or not KGRegistry.is_active():
            return

        try:
            logger.info(f"🚀 [KG-Pipeline] 开始处理切片: {chunk_id[:8]}...")
            # 从注册表动态获取 Agent 实例
            extractor = KGRegistry.get_agent("extractor")
            inspector = KGRegistry.get_agent("inspector")
            resolver = KGRegistry.get_agent("resolution")
            es_indexer = KGRegistry.get_agent("es_indexer")
            if es_indexer:
                for ent in final_kb['entities']:
                    es_indexer.index_entity(ent['name'], vid)

            if not all([extractor, inspector, resolver]):
                return

            # A. 联合抽取
            breadcrumb = chunk.metadata.get("breadcrumb", "")
            raw_kb = extractor.run(chunk.content, breadcrumb)

            # B. 质量审查
            refined_kb = inspector.run(chunk.content, raw_kb)

            # C. 梯度消歧
            final_kb = resolver.run(refined_kb.get('entities', []), refined_kb.get('relations', []))

            # D. 入库
            self.nebula.upsert_graph(final_kb, chunk_id)

        except Exception as ex:
            logger.warning(f"⚠️ [KG Pipeline] Failed: {ex}")