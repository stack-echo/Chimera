import functools
import json
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from google.protobuf.message import Message
from google.protobuf.json_format import MessageToDict

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

tracer = trace.get_tracer("chimera.runtime")

def setup_otel(service_name="chimera-agents-runtime", endpoint="http://localhost:4317"):
    """
    初始化 OpenTelemetry 并在全局注册。
    这个函数需要在 main.py 启动时最先调用。
    """
    # 1. 定义资源信息（显示在 SigNoz 的服务列表里）
    resource = Resource(attributes={
        "service.name": service_name
    })

    # 2. 创建 Tracer 提供者
    provider = TracerProvider(resource=resource)

    # 3. 配置导出器（指向 SigNoz 的数据接收端口）
    # insecure=True 是因为本地 SigNoz 默认没开 TLS
    otlp_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)

    # 4. 添加处理器（Batch 模式性能更好）
    span_processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(span_processor)

    # 5. 设置全局全局追踪器
    trace.set_tracer_provider(provider)

    print(f"✅ OpenTelemetry initialized for {service_name}, exporting to {endpoint}")

def trace_agent(agent_name: str):
    """
    亮点：自动捕获 Agent 执行全过程的 Payload 和上下文
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # 1. 精准提取 Payload (跳过 self)
            raw_input = args[0] if args else kwargs

            # 2. 转换 Protobuf 对象为可序列化字典
            if isinstance(raw_input, Message):
                serializable_input = MessageToDict(raw_input)
            else:
                serializable_input = raw_input

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