import logging
from typing import Any

from rpc import runtime_pb2, runtime_pb2_grpc
from core.managers.etl_manager import ETLManager
from core.managers.inference_manager import InferenceManager
from core.stores.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)

class ChimeraRuntimeService(runtime_pb2_grpc.RuntimeServiceServicer):
    def __init__(self, qdrant_store: QdrantStore, nebula_store: Any = None):
        """
        依赖注入：Service 层不关心具体的存储实现细节，只负责传递给 Manager
        """
        # 初始化业务逻辑管理器
        self.etl_mgr = ETLManager(qdrant_store, nebula_store)
        self.inf_mgr = InferenceManager(qdrant_store, nebula_store)
        logger.info("✅ RuntimeService initialized (Controller Mode)")

    def SyncDataSource(self, request, context):
        """
        ETL 数据同步接口 (Unary Call)
        Go 端调用此接口触发数据清洗和入库
        """
        try:
            # 调用 Manager 执行逻辑
            # Manager 是个生成器，但因为 Proto 定义是 Unary (非流式)，
            # 我们在这里消费完生成器，只返回最后的结果。
            # (如果未来需要实时进度条，需修改 Proto 为 stream SyncResponse)
            final_stats = {"chunks": 0, "pages": 0}

            iterator = self.etl_mgr.sync_datasource(
                kb_id=request.kb_id,
                source_id=request.datasource_id,
                source_type=request.type,
                config_json=request.config_json
            )

            for progress in iterator:
                # 可以在这里打印日志或者发送 metrics
                if "chunks" in progress:
                    final_stats = progress

            return runtime_pb2.SyncResponse(
                success=True,
                chunks_count=final_stats.get("chunks", 0),
                page_count=final_stats.get("pages", 0)
            )

        except Exception as e:
            logger.error(f"❌ RPC Sync Failed: {str(e)}")
            return runtime_pb2.SyncResponse(
                success=False,
                error_msg=str(e)
            )

    def RunAgent(self, request, context):
        """
        智能体对话接口 (Server Streaming)
        """
        try:
            # 调用 Manager 获取事件流
            iterator = self.inf_mgr.run_chat(
                query=request.query,
                history=request.history,
                app_config_json=request.app_config_json
            )

            # 将 Manager 返回的 Dict 转换为 Protobuf Message
            for event in iterator:
                event_type = event.get("type")

                # 1. 思考过程
                if event_type == "thought":
                    meta = event.get("meta", {})
                    yield runtime_pb2.RunAgentResponse(
                        type="thought",
                        payload=event.get("payload", ""),
                        meta=runtime_pb2.AgentMeta(
                            node_name=meta.get("node_name", "Agent"),
                            trace_id=meta.get("trace_id", ""),
                            duration_ms=meta.get("duration_ms", 0)
                        )
                    )

                # 2. 增量文本 (打字机效果)
                elif event_type == "delta":
                    yield runtime_pb2.RunAgentResponse(
                        type="delta",
                        payload=event.get("payload", "")
                    )

                # 3. 引用来源
                elif event_type == "reference":
                    yield runtime_pb2.RunAgentResponse(
                        type="reference",
                        payload=event.get("payload", "[]")
                    )

                # 4. 执行摘要 (End of Stream)
                elif event_type == "summary":
                    s = event.get("summary", {})
                    yield runtime_pb2.RunAgentResponse(
                        type="summary",
                        summary=runtime_pb2.RunSummary(
                            total_tokens=s.get("total_tokens", 0),
                            prompt_tokens=s.get("prompt_tokens", 0),
                            completion_tokens=s.get("completion_tokens", 0),
                            total_duration_ms=s.get("total_duration_ms", 0),
                            final_status=s.get("final_status", "success")
                        )
                    )

                # 5. 逻辑错误
                elif event_type == "error":
                    yield runtime_pb2.RunAgentResponse(
                        type="error",
                        payload=event.get("payload", "Unknown Logic Error")
                    )

        except Exception as e:
            # 系统级崩溃捕获
            logger.error(f"❌ RPC RunAgent Crashed: {str(e)}")
            yield runtime_pb2.RunAgentResponse(
                type="error",
                payload=f"Internal Server Error: {str(e)}"
            )