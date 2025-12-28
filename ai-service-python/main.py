import logging
import sys
import os
from concurrent import futures
import grpc
from config import Config

# 1. 确保能找到 rpc 包 (防止 ModuleNotFoundError)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 2. 引入新生成的 rpc 代码
from rpc import rag_pb2_grpc

# 3. 引入你的业务服务 (稍后我们需要去修改这个文件)
from service.rag_service import ChimeraLLMService

def serve():
    # 增加 max_workers 以支持并发的 ETL 任务
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=Config.MAX_WORKERS if hasattr(Config, 'MAX_WORKERS') else 10),
        options=[
            ('grpc.max_send_message_length', Config.MAX_MESSAGE_LENGTH),
            ('grpc.max_receive_message_length', Config.MAX_MESSAGE_LENGTH),
        ]
    )

    # 🔥 核心修改：注册 RagService (以前是 LLMService)
    # 注意：这里调用的是新生成的 add_RagServiceServicer_to_server
    rag_pb2_grpc.add_RagServiceServicer_to_server(ChimeraLLMService(), server)

    # 监听端口
    server.add_insecure_port(f'[::]:{Config.PORT}')
    logging.info(f"🚀 Chimera Brain v0.4.0 (SaaS Edition) running on port {Config.PORT}...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    serve()