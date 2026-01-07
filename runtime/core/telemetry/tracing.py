import functools
import json
import os

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from google.protobuf.message import Message
from google.protobuf.json_format import MessageToDict
import collections

OTEL_ENABLED = os.getenv("ENABLE_OTEL", "true").lower() == "true"

def setup_otel(service_name="chimera-brain-python", endpoint="http://localhost:4317"):
    if not OTEL_ENABLED:
        print("ℹ️ OTel tracing is disabled.")
        return

    resource = Resource(attributes={"service.name": service_name, "service.version": "v0.6.0"})
    provider = TracerProvider(resource=resource)

    try:
        # 增加超时控制，防止 SigNoz 连不上卡死系统
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True, timeout=2)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        print(f"✅ OTel initialized: exporting to {endpoint}")
    except Exception as e:
        print(f"⚠️ OTel Init Failed: {e}")

def convert_to_serializable(obj):
    """
    递归转换所有对象为原生 Python 类型
    """
    if isinstance(obj, Message):
        return MessageToDict(obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, collections.abc.Mapping):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, collections.abc.Iterable) and not isinstance(obj, (bytes, str)):
        return [convert_to_serializable(item) for item in obj]
    return str(obj)

def trace_agent(agent_name: str):
    """
    亮点：自动捕获 Agent 执行全过程的 Payload 和上下文
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not OTEL_ENABLED:
                return func(self, *args, **kwargs)

            # 1. 精准提取 Payload (跳过 self)
            raw_input = args[0] if args else kwargs

            # 2. 转换 Protobuf 对象为可序列化字典
            serializable_input = convert_to_serializable(raw_input)

            with tracer.start_as_current_span(f"🤖 Agent:{agent_name}") as span:
                span.set_attribute("chimera.agents.name", agent_name)
                # 记录格式化后的输入
                span.set_attribute("chimera.input.payload",
                                   json.dumps(serializable_input, ensure_ascii=False))

                if hasattr(self, 'prompt_path'):
                    span.set_attribute("chimera.prompts.path", self.prompt_path)

                try:
                    result = func(self, *args, **kwargs)

                    # 3. 🔥 核心逻辑：处理流式响应 (ChatStream)
                    if hasattr(result, '__iter__') and not isinstance(result, (list, dict, str)):
                        def generator_wrapper():
                            full_response = []
                            try:
                                for chunk in result:
                                    # 如果 chunk 是 Protobuf 消息也需要转换
                                    c_data = MessageToDict(chunk) if isinstance(chunk, Message) else chunk
                                    full_response.append(c_data)
                                    yield chunk
                                # 流结束后，一次性记录完整的变异输出到 SigNoz
                                span.set_attribute("chimera.output.payload",
                                                   json.dumps(full_response, ensure_ascii=False))
                                span.set_status(Status(StatusCode.OK))
                            except Exception as ge:
                                span.record_exception(ge)
                                span.set_status(Status(StatusCode.ERROR, str(ge)))
                                raise ge
                        return generator_wrapper()

                    # 4. 处理普通非流式返回
                    serializable_output = MessageToDict(result) if isinstance(result, Message) else result
                    span.set_attribute("chimera.output.payload",
                                       json.dumps(serializable_output, ensure_ascii=False))
                    span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise e
        return wrapper
    return decorator