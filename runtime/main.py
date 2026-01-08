import logging
import grpc
import os
import sys
from concurrent import futures
from config import Config

# OpenTelemetry
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
from core.telemetry.tracing import setup_otel

# Core Stores
from core.stores.qdrant_store import QdrantStore
import core.connectors.file

# Service & Loader
from service.runtime_service import ChimeraRuntimeService
from loader import load_enterprise_plugins # 👈 引入刚才写的加载器

# Generated RPC Path Fix
rpc_path = os.path.join(os.path.dirname(__file__), 'rpc')
if rpc_path not in sys.path:
    sys.path.insert(0, rpc_path)
from rpc import runtime_pb2_grpc

def serve():
    # 1. 初始化日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # 2. 尝试加载企业版插件 (飞书、钉钉等)
    # 这会触发 ConnectorFactory.register，使得后续逻辑能找到这些连接器
    has_enterprise = load_enterprise_plugins()

    # 3. 初始化链路追踪
    setup_otel(service_name=Config.SERVICE_NAME, endpoint=Config.OTEL_ENDPOINT)

    # 4. 初始化存储层
    logger.info("📦 Initializing Storage Engines...")

    # Qdrant (Core - 必须)
    try:
        qdrant_store = QdrantStore()
    except Exception as e:
        logger.critical(f"❌ Qdrant init failed: {e}")
        sys.exit(1)

    # Nebula (Enterprise - 可选)
    nebula_store = None
    # 只有当检测到企业版环境，且配置文件里有 Nebula 地址时，才尝试连接
    if has_enterprise and getattr(Config, "NEBULA_HOST", None):
        try:
            # 动态 Import，避免 Core 版因缺少库而报错
            # 注意：物理拆分后，这个路径可能是 enterprise.core.stores.graph_store
            # 为了兼容当前路径，我们先尝试标准路径，如果报错再尝试 enterprise 路径
            try:
                from core.stores.graph_store import NebulaStore
            except ImportError:
                from enterprise.core.stores.graph_store import NebulaStore

            nebula_store = NebulaStore(Config)
            logger.info("✅ NebulaGraph Connected (GraphRAG Enabled)")
        except ImportError:
            logger.warning("⚠️ NebulaStore module not found in Enterprise package.")
        except Exception as e:
            logger.warning(f"⚠️ NebulaGraph connection failed (Logic will degrade to Vector-Only): {e}")

    # 5. 初始化 gRPC Server
    instrumentor = GrpcInstrumentorServer()
    if not instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.instrument()

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=getattr(Config, 'MAX_WORKERS', 10)),
        options=[
            ('grpc.max_send_message_length', Config.MAX_MESSAGE_LENGTH),
            ('grpc.max_receive_message_length', Config.MAX_MESSAGE_LENGTH),
        ]
    )

    # 6. 注册服务 (注入 Store 依赖)
    # RuntimeService 现在是一个纯 Controller，它会将 Store 传给 Managers
    runtime_pb2_grpc.add_RuntimeServiceServicer_to_server(
        ChimeraRuntimeService(qdrant_store, nebula_store),
        server
    )

    # 7. 启动
    server.add_insecure_port(f'[::]:{Config.PORT}')
    logger.info(f"🧠 Chimera Runtime v0.6.0 running on port {Config.PORT}...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()