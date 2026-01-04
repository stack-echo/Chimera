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

# --- OTel 初始化 ---
resource = Resource(attributes={
    "service.name": "chimera-agents-runtime",
    "service.version": "v0.5.0"
})
provider = TracerProvider(resource=resource)
# 默认发送到 SigNoz 的 4317 端口
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# 定义全局开关变量
OTEL_ENABLED = os.getenv("ENABLE_OTEL", "true").lower() == "true"

tracer = trace.get_tracer("chimera.runtime")

def setup_otel(service_name="chimera-brain-python", endpoint="http://localhost:4317"):
    """
    增强版 OTel 初始化：支持开关、超时控制、异常隔离
    """
    # 1. 增加开关：方便本地调试时一键关闭
    # 在 .env 中设置 ENABLE_OTEL=false 即可关闭
    if os.getenv("ENABLE_OTEL", "true").lower() == "false":
        print("ℹ️ OpenTelemetry tracing is disabled by environment variable.")
        return

    try:
        resource = Resource(attributes={
            "service.name": service_name,
            "service.version": "v0.6.0"
        })

        # 2. 增加超时控制 (timeout=2)
        # 如果 SigNoz 2秒内连不上，不再死磕，减少对主业务的影响
        otlp_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            insecure=True,
            timeout=2  # 🔥 关键：防止 UNAVAILABLE 导致的系统阻塞
        )

        # 3. 优化 Batch 处理器
        span_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=512,          # 内存缓冲区大小
            schedule_delay_millis=5000,   # 每5秒发送一次，减少 CPU 占用
        )

        provider = TracerProvider(resource=resource)
        provider.add_span_processor(span_processor)

        # 4. 解决 "Overriding of current TracerProvider is not allowed" 警告
        try:
            trace.set_tracer_provider(provider)
            print(f"✅ OpenTelemetry initialized for {service_name}, exporting to {endpoint}")
        except ValueError:
            # 说明已经设置过了，静默处理
            pass

    except Exception as e:
        # 5. 异常隔离：Tracing 失败绝对不能导致 main.py 启动失败
        print(f"⚠️ OpenTelemetry initialization failed: {e}. The app will run without tracing.")

def convert_to_serializable(obj):
    """
    更强大的递归转换：处理 gRPC 的 RepeatedCompositeContainer 和字典
    """
    if isinstance(obj, Message):
        return MessageToDict(obj)

    if isinstance(obj, collections.abc.Iterable) and not isinstance(obj, (str, dict, bytes)):
        return [convert_to_serializable(item) for item in obj]

    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}

    return obj

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