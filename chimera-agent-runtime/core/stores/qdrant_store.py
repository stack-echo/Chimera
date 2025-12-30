import logging
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from config import Config

logger = logging.getLogger(__name__)

class QdrantStore:
    def __init__(self):
        self.client = QdrantClient(
            host=Config.QDRANT_HOST,
            port=Config.QDRANT_PORT,
        )
        # 🔥 修正：统一集合名称为 chimera_docs (与 Go 端保持一致)
        self.collection_name = "chimera_docs"
        self.vector_size = 384

        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"✅ Qdrant 集合 '{self.collection_name}' 已就绪")
        except Exception:
            logger.info(f"🚧 Qdrant 集合不存在，正在创建: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE
                )
            )
            # 创建索引
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="kb_id",
                field_schema=models.PayloadSchemaType.INTEGER
            )

    def upsert_chunks(self, chunks: List[Dict[str, Any]]):
        points = []
        for idx, chunk in enumerate(chunks):
            # 确保 id 存在
            import uuid
            point_id = chunk.get("id") or str(uuid.uuid4())

            points.append(models.PointStruct(
                id=point_id,
                vector=chunk["vector"],
                payload=chunk["payload"]
            ))

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        logger.info(f"💾 已向 Qdrant 写入 {len(points)} 条向量数据")

    def search(self, query_vector: List[float], kb_ids: List[int], top_k: int = 5):
        """
        带过滤的搜索
        """
        # 构造过滤器
        search_filter = None
        if kb_ids:
            # 兼容处理：确保 kb_ids 是 list
            if not isinstance(kb_ids, list):
                kb_ids = [kb_ids]

            search_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="kb_id",
                        match=models.MatchAny(any=kb_ids)
                    )
                ]
            )

        # 🔥 核心修复：防止 search 方法报错，增加 fallback
        try:
            # 优先尝试标准的 search 方法
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=top_k
            )
        except AttributeError:
            # 如果真的报 AttributeError，尝试用 search_batch (旧版) 或 query_points (新版底层)
            logger.warning("⚠️ QdrantClient.search 方法未找到，尝试使用 query_points...")
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=search_filter,
                limit=top_k
            ).points

        # 格式化结果
        formatted = []
        for hit in results:
            formatted.append({
                "content": hit.payload.get("content", ""),
                "score": hit.score,
                "metadata": hit.payload
            })

        return formatted