import sys
import os
import logging
import tempfile
import time
from dotenv import load_dotenv
import uuid
import requests
import json

# 加载环境变量
load_dotenv()

# 确保能导入 rpc 目录
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'rpc'))

# 全局初始化一个 Session 对象
# 它可以自动维持 TCP 长连接，避免每次握手
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
http_session.mount('http://', adapter)

# 🔥 1. 导入新的 Proto 定义
from rpc import rag_pb2
from rpc import rag_pb2_grpc

# 引入核心组件
from core.llm import LLMClient
from core.embedding import EmbeddingModel
from tools.pdf_parser import PDFParser

# 引入存储组件 (MinIO & Qdrant)
from minio import Minio
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from config import Config # 假设你把配置都放在这里了

# 继承新的 RagServiceServicer
class ChimeraLLMService(rag_pb2_grpc.RagServiceServicer):
    def __init__(self):
        logging.info("🛠️ 初始化 Chimera RAG Service...")

        # 1. 现有组件
        self.llm = LLMClient()
        EmbeddingModel.get_instance() # 预加载模型

        # 2. 🔥 新增：初始化 MinIO (用于下载文件)
        # 建议后续封装到 core/storage.py
        self.minio = Minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_AK", "chimera_minio"),
            secret_key=os.getenv("MINIO_SK", "chimera_minio_secret"),
            secure=False
        )

        # 3. 🔥 新增：初始化 Qdrant (用于写入向量)
        # 建议后续封装到 core/vector_store.py
        self.qdrant = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", 6333))
        )
        self.collection_name = "chimera_docs"

    # ----------------------------------------------------------------
    # 1. 聊天接口 (ChatStream) - 适配 v0.4.0
    # ----------------------------------------------------------------
    def ChatStream(self, request, context):
        logging.info(f"[Chat] 收到提问: {request.query} (KB={request.kb_id}, Org={request.org_id})")

        try:
            # ==========================================
            # Step 1: Embedding
            # ==========================================
            query_vector = EmbeddingModel.encode(request.query)
            if hasattr(query_vector, "tolist"):
                query_vector = query_vector.tolist()

            # ==========================================
            # Step 2: 构建 Filter (手动构建字典，不依赖 SDK 对象)
            # ==========================================
            # Qdrant 的 Filter JSON 结构
            filter_payload = None

            must_conditions = []
            if request.kb_id > 0:
                must_conditions.append({
                    "key": "kb_id",
                    "match": {"value": request.kb_id}
                })
            elif request.org_id > 0:
                must_conditions.append({
                    "key": "org_id",
                    "match": {"value": request.org_id}
                })

            if must_conditions:
                filter_payload = {"must": must_conditions}

            # ==========================================
            # Step 3: 原生 HTTP 请求 (核武器级修复 ☢️)
            # ==========================================
            # 拼接 Qdrant 搜索接口 URL
            qdrant_host = os.getenv("QDRANT_HOST", "localhost")
            qdrant_port = os.getenv("QDRANT_PORT", "6333")
            url = f"http://{qdrant_host}:{qdrant_port}/collections/{self.collection_name}/points/search"

            # 构造 Request Body
            payload = {
                "vector": query_vector,
                "limit": 15,
                "with_payload": True,
                "score_threshold": 0
            }
            if filter_payload:
                payload["filter"] = filter_payload

            logging.info(f"🚀 发送 HTTP 搜索请求: {url}")

            # 发送请求
            response = http_session.post(url, json=payload, timeout=5)

            if response.status_code != 200:
                logging.error(f"Qdrant HTTP Error: {response.text}")
                raise Exception(f"Search failed with status {response.status_code}")

            # 解析结果
            # Qdrant HTTP 接口返回格式: { "result": [ { "payload": {...}, "score": 0.9 }, ... ], ... }
            resp_json = response.json()
            search_results = resp_json.get("result", [])

            logging.info(f"🔍 检索到 {len(search_results)} 条相关上下文")

            # ==========================================
            # Step 4: 构建 Context (解析原生 JSON)
            # ==========================================
            if not search_results:
                context_str = "没有找到相关的上下文信息。"
            else:
                context_parts = []
                for idx, hit in enumerate(search_results):
                    # HTTP 返回的 hit 是字典
                    payload = hit.get("payload", {})

                    if payload:
                        content = payload.get("content", "")
                        file_name = payload.get("file_name", "unknown")
                        page_num = payload.get("page_number", 0)

                        part = f"片段{idx+1}: {content}\n来源: <<{file_name}|{page_num}>>"
                        context_parts.append(part)

                context_str = "\n\n".join(context_parts)

            # ==========================================
            # Step 5: 调用 LLM (保持不变)
            # ==========================================
            final_system_prompt = f"""
            你是一个专业的科研助手 (Chimera-RAG)。
            请基于以下【参考上下文】回答用户的【问题】。

            【参考上下文】
            {context_str}

            【回答要求】
            1. 必须严格引用上述上下文中的信息。
            2. 如果上下文没有提到，请直接说不知道，不要编造。
            3. 引用格式保持为：<<文件名|页码>>
            """

            generator = self.llm.stream_chat(request.query, system_prompt=final_system_prompt)

            for text_delta in generator:
                yield rag_pb2.ChatReply(answer_delta=text_delta)

        except Exception as e:
            import traceback
            traceback.print_exc()
            logging.error(f"❌ RAG 流程出错: {e}")
            yield rag_pb2.ChatReply(answer_delta=f"**System Error**: {str(e)}")

    # ----------------------------------------------------------------
    # 2. 文档入库接口 (ParseAndIngest) - 核心重构
    # ----------------------------------------------------------------
    def ParseAndIngest(self, request, context):
        """
        ETL 管道：MinIO下载 -> Docling解析 -> 向量化 -> Qdrant入库
        """
        logging.info(f"\n📥 [ETL] 开始处理任务: {request.file_name} (Path: {request.storage_path})")

        start_time = time.time()

        # 使用临时文件处理，处理完自动删除
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_file:
            try:
                # --- Step 1: 从 MinIO 下载 ---
                logging.info(f"  ⬇️ 正在下载: {os.getenv('MINIO_BUCKET', 'chimera-docs')}/{request.storage_path}")
                self.minio.fget_object(
                    os.getenv("MINIO_BUCKET", "chimera-docs"),
                    request.storage_path,
                    tmp_file.name
                )

                # 🛡️ 安全检查：确认文件真的下载下来了且不为空
                file_size = os.path.getsize(tmp_file.name)
                if file_size == 0:
                    raise Exception("MinIO 下载的文件为空！")
                logging.info(f"  ✅ 下载完成，文件大小: {file_size} bytes")

                # --- Step 2: 调用现有的 PDFParser ---
                logging.info("  📖 调用 Docling 解析中...")
                raw_chunks = PDFParser.parse_and_chunk(
                    file_source=tmp_file.name,
                    filename=request.file_name
                )

                if not raw_chunks:
                    return rag_pb2.ParseResponse(success=False, error_msg="解析结果为空", chunk_count=0)

                # --- Step 3: 向量化 & 准备 Qdrant 数据 ---
                points = []
                logging.info(f"  🧠 正在向量化 {len(raw_chunks)} 个切片...")

                for idx, item in enumerate(raw_chunks):
                    content = item['content']
                    page_num = item.get('page', 1)

                    # 调用 Core Embedding
                    vector = EmbeddingModel.encode(content)

                    # 构造 Payload (元数据)
                    payload = {
                        "content": content,
                        "file_name": request.file_name,
                        "page_number": page_num,
                        "doc_id": request.doc_id, # 关联 Postgres ID
                        "kb_id": request.kb_id,   # 知识库隔离
                        "org_id": request.org_id  # 组织隔离
                    }

                    # 使用 uuid5 + DNS 命名空间，保证 "3_0" 永远转换成同一个 UUID
                    unique_str = f"{request.doc_id}_{idx}"
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_str))

                    points.append(rest.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    ))

                # --- Step 4: 写入 Qdrant ---
                logging.info(f"  💾 写入 Qdrant ({len(points)} points)...")
                self.qdrant.upsert(
                    collection_name=self.collection_name,
                    points=points
                )

                duration = time.time() - start_time
                logging.info(f"✅ [Success] ETL 完成，耗时 {duration:.2f}s")

                return rag_pb2.ParseResponse(
                    success=True,
                    chunk_count=len(points),
                    page_count=0 # 如果 PDFParser 返回了总页数可填这里
                )

            except Exception as e:
                import traceback
                traceback.print_exc()
                logging.error(f"❌ ETL 失败: {str(e)}")
                return rag_pb2.ParseResponse(
                    success=False,
                    error_msg=str(e),
                    chunk_count=0
                )