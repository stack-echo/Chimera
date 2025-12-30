import logging
import grpc
import os
import sys
from concurrent import futures
from config import Config

# OpenTelemetry
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
from core.telemetry.tracing import setup_otel

# Stores
from core.stores.graph_store import NebulaStore
from core.stores.qdrant_store import QdrantStore # 🔥 新增

# Service
from service.runtime_service import ChimeraRuntimeService # 🔥 替换原有的 RagService

# Generated RPC
rpc_path = os.path.join(os.path.dirname(__file__), 'rpc')
if rpc_path not in sys.path:
    sys.path.insert(0, rpc_path)
from rpc import runtime_pb2_grpc # 注意这里变成了 runtime_pb2_grpc

def serve():
    # 1. 初始化日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 2. 初始化 OTel
    setup_otel(service_name=Config.SERVICE_NAME, endpoint=Config.OTEL_ENDPOINT)

    # 3. 初始化存储层 (单例模式)
    logger = logging.getLogger(__name__)
    logger.info("📦 Initializing Storage Engines...")

    nebula_store = NebulaStore(Config)
    qdrant_store = QdrantStore() # 内部会自动连接并建表

    # 4. 初始化 gRPC Server
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

    # 5. 注册服务 (注入依赖)
    runtime_pb2_grpc.add_RuntimeServiceServicer_to_server(
        ChimeraRuntimeService(nebula_store, qdrant_store),
        server
    )

    # 6. 启动
    server.add_insecure_port(f'[::]:{Config.PORT}')
    logger.info(f"🧠 Chimera Runtime v0.5.0 (Platform Edition) running on port {Config.PORT}...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()