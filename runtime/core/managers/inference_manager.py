import json
import time
import logging
import traceback
from typing import Generator, Dict, Any, List

from opentelemetry import trace
from workflows.chat_flow import ChatWorkflow

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class InferenceManager:
    def __init__(self, qdrant_store, nebula_store=None):
        """
        初始化推理管理器
        :param qdrant_store: 向量存储 (Core)
        :param nebula_store: 图存储 (Enterprise, 可选)
        """
        self.qdrant = qdrant_store
        self.nebula = nebula_store

    def run_chat(self, query: str, history: List[Any], app_config_json: str) -> Generator[Dict[str, Any], None, None]:
        """
        执行对话工作流
        :param query: 用户问题
        :param history: 历史记录 (gRPC Message list)
        :param app_config_json: 应用配置 (含 kb_ids, org_id)
        :yield: 标准化的事件字典 (type, payload, meta)
        """
        start_time = time.time()

        # 1. 准备统计数据
        usage_stats = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

        # 获取当前 TraceID (用于返回给前端展示)
        current_span = trace.get_current_span()
        trace_id = format(current_span.get_span_context().trace_id, "032x")

        try:
            # 2. 解析配置
            app_config = json.loads(app_config_json)
            kb_ids = app_config.get("kb_ids", [])

            # 3. 初始化工作流 (每次请求可能针对不同的 KB，所以在这里初始化)
            # 注意：ChatWorkflow 内部已经做了对 nebula 为 None 的容错处理 (见 Phase 1 步骤 4)
            workflow = ChatWorkflow(self.nebula, self.qdrant, kb_ids)

            # 4. 构造初始状态
            initial_state = {
                "query": query,
                "history": history,
                "app_config": app_config
            }

            # 5. 执行工作流并处理流式事件
            for event in workflow.run_stream(initial_state):

                # A. 思考/推理过程
                if event["type"] == "thought":
                    yield {
                        "type": "thought",
                        "payload": event["content"],
                        "meta": {
                            "node_name": event.get("node", "Agent"),
                            "trace_id": trace_id,
                            "duration_ms": event.get("duration", 0)
                        }
                    }

                # B. 答案片段
                elif event["type"] == "delta":
                    yield {
                        "type": "delta",
                        "payload": event["content"]
                    }

                # C. 引用文档
                elif event["type"] == "reference":
                    yield {
                        "type": "reference",
                        "payload": json.dumps(event["docs"]) # 序列化后返回
                    }

                # D. Token 统计
                elif event["type"] == "usage":
                    u = event["usage"]
                    usage_stats["prompt_tokens"] += u.get("prompt_tokens", 0)
                    usage_stats["completion_tokens"] += u.get("completion_tokens", 0)
                    usage_stats["total_tokens"] += u.get("total_tokens", 0)

                elif event["type"] == "subgraph":
                    yield {
                        "type": "subgraph",
                        "payload": event["payload"]
                    }

        except Exception as e:
            logger.error(f"❌ [Inference] Error: {str(e)}")
            logger.error(traceback.format_exc())
            yield {
                "type": "error",
                "payload": f"Inference Error: {str(e)}"
            }

        finally:
            # 6. 生成最终摘要 (Summary)
            duration = int((time.time() - start_time) * 1000)
            logger.info(f"📊 [Inference Done] Tokens={usage_stats['total_tokens']} Time={duration}ms")

            yield {
                "type": "summary",
                "summary": {
                    "total_tokens": usage_stats["total_tokens"],
                    "prompt_tokens": usage_stats["prompt_tokens"],
                    "completion_tokens": usage_stats["completion_tokens"],
                    "total_duration_ms": duration,
                    "final_status": "success"
                }
            }