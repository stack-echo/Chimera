import json
import logging
import time
import traceback
from typing import Generator

# gRPC 相关
import grpc
from rpc import runtime_pb2, runtime_pb2_grpc

# 核心组件
from core.stores.qdrant_store import QdrantStore
from core.stores.graph_store import NebulaStore
from core.llm.embedding import EmbeddingModel
from core.connectors.file import FileConnector
# 假设后续会有 FeishuConnector
# from core.connectors.feishu import FeishuConnector

# 工作流 (稍后我们需要调整它以适应新架构)
from workflows.chat_flow import ChatWorkflow

from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class ChimeraRuntimeService(runtime_pb2_grpc.RuntimeServiceServicer):
    def __init__(self, nebula_store: NebulaStore, qdrant_store: QdrantStore):
        """
        依赖注入：在 main.py 中初始化好存储层传进来
        """
        self.nebula = nebula_store
        self.qdrant = qdrant_store
        # 初始化 Embedding 模型 (单例)
        self.embed_model = EmbeddingModel.get_instance()
        logger.info("✅ RuntimeService initialized with Storage Engines")

    def SyncDataSource(self, request, context):
        """
        ETL 核心入口：数据源同步
        支持从不同源 (File, Feishu) 读取 -> 清洗 -> 向量化 -> 存储
        """
        start_time = time.time()
        logger.info(f"🔄 [ETL] 开始同步 SourceID={request.datasource_id} (Type={request.type})")

        try:
            config = json.loads(request.config_json)
            connector = None

            # 1. 工厂模式：选择连接器
            if request.type == "file":
                # file_path 通常是 minio 的路径或本地临时路径
                connector = FileConnector(request.kb_id, request.datasource_id, config)
            elif request.type == "feishu":
                # connector = FeishuConnector(request.kb_id, request.datasource_id, config)
                raise NotImplementedError("飞书连接器开发中")
            else:
                return runtime_pb2.SyncResponse(success=False, error_msg=f"未知的类型: {request.type}")

            chunks_buffer = []
            total_chunks = 0

            # 2. 流式处理：读取 -> 向量化
            # connector.load() 是一个生成器，返回 DocumentChunk 对象
            for chunk in connector.load():
                # 计算向量 (384维)
                vector = self.embed_model.encode(chunk.content)

                # 组装 Qdrant 需要的数据结构
                chunks_buffer.append({
                    "vector": vector,
                    "payload": {
                        "content": chunk.content,
                        "kb_id": request.kb_id,
                        "source_id": request.datasource_id,
                        **chunk.metadata # 合并其他元数据 (如 page_num)
                    }
                })

                # 批处理写入 (每 50 条写一次，防止内存溢出)
                if len(chunks_buffer) >= 50:
                    self.qdrant.upsert_chunks(chunks_buffer)
                    total_chunks += len(chunks_buffer)
                    chunks_buffer = []

            # 写入剩余的
            if chunks_buffer:
                self.qdrant.upsert_chunks(chunks_buffer)
                total_chunks += len(chunks_buffer)

            logger.info(f"✅ [ETL] 同步完成。共写入 {total_chunks} 个切片，耗时 {time.time() - start_time:.2f}s")

            return runtime_pb2.SyncResponse(success=True, chunks_count=total_chunks)

        except Exception as e:
            logger.error(f"❌ [ETL] 同步失败: {str(e)}")
            logger.error(traceback.format_exc())
            return runtime_pb2.SyncResponse(success=False, error_msg=str(e))

    def RunAgent(self, request, context):
        """
        推理核心入口：执行 Agent
        """
        start_time = time.time() # ⏱️ 计时开始
        # ... TraceID 获取 ...

        # 初始化统计
        usage_stats = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        status = "success"
        # 获取当前的 TraceID (由 Go 端透传或自动生成)
        current_span = trace.get_current_span()
        trace_id = format(current_span.get_span_context().trace_id, "032x")

        logger.info(f"🤖 [RunAgent] AppID={request.app_id} Query={request.query[:20]}...")

        try:
            # 1. 解析配置
            app_config = json.loads(request.app_config_json)
            # 提取 kb_ids, 例如: [1, 2]
            kb_ids = app_config.get("kb_ids", [])

            # 2. 初始化工作流 (LangGraph)
            # 注意：我们将 qdrant_store 和 kb_ids 传入工作流，这样它才能去检索正确的数据
            workflow = ChatWorkflow(self.nebula, self.qdrant, kb_ids)

            # 构造初始状态
            initial_state = {
                "query": request.query,
                "history": request.history, # 暂时透传
                "app_config": app_config
            }

            # 3. 运行工作流并流式返回
            # 假设 workflow.run_stream 返回的是一个生成器，产生事件
            for event in workflow.run_stream(initial_state):

                # A. 处理思考事件 (thought)
                if event["type"] == "thought":
                    yield runtime_pb2.RunAgentResponse(
                        type="thought",
                        payload=event["content"],
                        meta=runtime_pb2.AgentMeta(
                            node_name=event.get("node", "Agent"),
                            trace_id=trace_id,
                            duration_ms=event.get("duration", 0)
                        )
                    )

                # B. 处理答案片段 (Delta)
                elif event["type"] == "delta":
                    yield runtime_pb2.RunAgentResponse(
                        type="delta",
                        payload=event["content"]
                    )

                # C. 处理引用 (Reference)
                elif event["type"] == "reference":
                    yield runtime_pb2.RunAgentResponse(
                        type="reference",
                        payload=json.dumps(event["docs"]) # 序列化引用列表
                    )

                # D. 捕获 Usage 事件
                elif event["type"] == "usage":
                    u = event["usage"]
                    usage_stats["prompt_tokens"] = u.get("prompt_tokens", 0)
                    usage_stats["completion_tokens"] = u.get("completion_tokens", 0)
                    usage_stats["total_tokens"] = u.get("total_tokens", 0)

        except Exception as e:
            logger.error(f"❌ [RunAgent] 执行异常: {str(e)}")
            yield runtime_pb2.RunAgentResponse(
                type="error",
                payload=f"System Error: {str(e)}"
            )

        finally:
            # 🔥 最终：发送 Summary
            duration = int((time.time() - start_time) * 1000)

            logger.info(f"📊 [Summary] Duration={duration}ms Tokens={usage_stats['total_tokens']}")

            yield runtime_pb2.RunAgentResponse(
                type="summary",
                summary=runtime_pb2.RunSummary(
                    total_tokens=usage_stats["total_tokens"],
                    prompt_tokens=usage_stats["prompt_tokens"],
                    completion_tokens=usage_stats["completion_tokens"],
                    total_duration_ms=duration,
                    final_status=status
                )
            )