import logging
import requests
import json
import numpy as np # 👈 引入 numpy 进行转换
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from config import Config

logger = logging.getLogger(__name__)

class QdrantStore:
    def __init__(self):
        # 锁定你的 Docker 映射端口
        self.host = getattr(Config, "QDRANT_HOST", "127.0.0.1")
        self.port = 26333
        self.collection_name = "chimera_docs"
        self.vector_size = 384

        # 初始化 SDK
        self.client = QdrantClient(host=self.host, port=self.port)
        self.api_url = f"http://{self.host}:{self.port}"

        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"✅ Qdrant 集合 '{self.collection_name}' 已就绪")
        except Exception:
            logger.info(f"🚧 尝试创建集合: {self.collection_name}")
            try:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(size=self.vector_size, distance=models.Distance.COSINE)
                )
            except:
                # SDK 失败则尝试 REST
                requests.put(f"{self.api_url}/collections/{self.collection_name}",
                             json={"vectors": {"size": self.vector_size, "distance": "Cosine"}})

    def search(self, query_vector: Any, kb_ids: List[int] = None, top_k: int = 5):
        """
        全平台兼容检索：自动处理 Numpy 转换 + SDK/REST 双路适配
        """
        # 1. 🔥 核心修复：强制将向量转为 Python 原生 List
        # 彻底解决 "ndarray is not JSON serializable" 报错
        if isinstance(query_vector, (np.ndarray, list)):
            if hasattr(query_vector, "tolist"):
                vector_list = query_vector.tolist()
            else:
                vector_list = list(query_vector)
        else:
            vector_list = query_vector

        # 2. 构造过滤器
        search_filter = None
        if kb_ids:
            search_filter = {"must": [{"key": "kb_id", "match": {"any": kb_ids}}]}

        # 3. 🚀 优先尝试 REST API (因为你的环境 SDK 方法似乎有幽灵 Bug)
        # 针对 v1.7.4 的标准路径: /collections/{name}/points/search
        try:
            logger.info(f"📡 正在通过 REST 接口执行召回 (Port: {self.port})...")
            payload = {
                "vector": vector_list,
                "limit": top_k,
                "with_payload": True,
                "filter": search_filter if kb_ids else None
            }
            resp = requests.post(
                f"{self.api_url}/collections/{self.collection_name}/points/search",
                json=payload,
                timeout=5
            )

            if resp.status_code == 200:
                results = resp.json().get("result", [])
                return self._parse_rest_results(results)
            else:
                logger.warning(f"⚠️ REST 检索返回非 200: {resp.text}")
        except Exception as e:
            logger.error(f"⚠️ REST 链路故障: {e}")

        # 4. 备份方案：尝试所有可能的 SDK 方法
        for m_name in ["search", "query_points"]:
            method = getattr(self.client, m_name, None)
            if method:
                try:
                    logger.info(f"🔍 尝试 SDK.{m_name} 备份路径...")
                    res = method(
                        collection_name=self.collection_name,
                        query_vector=vector_list,
                        limit=top_k,
                        with_payload=True
                    )
                    if hasattr(res, 'points'): res = res.points
                    return self._parse_sdk_results(res)
                except:
                    continue

        return []

    def _parse_rest_results(self, result_list):
        formatted = []
        for hit in result_list:
            formatted.append({
                "id": str(hit.get("id", "")),
                "content": hit.get("payload", {}).get("content", ""),
                "score": hit.get("score", 0.0),
                "metadata": hit.get("payload", {})
            })
        return formatted

    def _parse_sdk_results(self, sdk_list):
        formatted = []
        for hit in sdk_list:
            p = getattr(hit, "payload", {})
            formatted.append({
                "id": str(getattr(hit, "id", "")),
                "content": p.get("content", ""),
                "score": getattr(hit, "score", 0.0),
                "metadata": p
            })
        return formatted

    def upsert_chunks(self, chunks: List[Dict[str, Any]]):
        if not chunks: return
        points = [
            models.PointStruct(id=c["id"], vector=c["vector"], payload=c["payload"])
            for c in chunks
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"💾 写入 Qdrant: {len(points)} 条数据")