import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

class Config:
    # --- 基础服务配置 ---
    PORT = int(os.getenv("PORT", 50051))
    # 允许传输的大文件限制 (100MB)
    MAX_MESSAGE_LENGTH = 100 * 1024 * 1024
    # 并行任务数
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", 10))

    # --- 链路追踪配置 (OTel) ---
    OTEL_ENDPOINT = os.getenv("OTEL_ENDPOINT", "localhost:4317")
    SERVICE_NAME = "chimera-brain-python"

    # --- 模型与 AI 配置 ---
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    EMBEDDING_MODEL_PATH = os.getenv("EMBEDDING_MODEL_PATH", "AI-ModelScope/all-MiniLM-L6-v2")

    # --- 存储层配置 ---

    # 1. NebulaGraph 配置
    NEBULA_HOST = os.getenv("NEBULA_HOST", "127.0.0.1")
    NEBULA_PORT = int(os.getenv("NEBULA_PORT", 29669))
    NEBULA_USER = os.getenv("NEBULA_USER", "root")
    NEBULA_PASSWORD = os.getenv("NEBULA_PASSWORD", "nebula")
    NEBULA_SPACE = os.getenv("NEBULA_SPACE", "chimera_kb")

    # 2. Qdrant 配置
    QDRANT_HOST = os.getenv("QDRANT_HOST", "127.0.0.1")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", 26333))

    # 3. Redis 配置
    REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 26379))

    # 🔥 4. MinIO 配置 (新增)
    # 注意：本地运行时如果连 Docker 里的 MinIO，host 应该是 localhost:9000
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:29000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "chimera_minio")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "chimera_minio_secret")
    # 桶名称要和 Go 端保持一致
    MINIO_BUCKET = os.getenv("MINIO_BUCKET", "chimera-docs")

    # --- 业务参数 ---
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))

    @staticmethod
    def validate():
        required_keys = {
            "DEEPSEEK_API_KEY": Config.DEEPSEEK_API_KEY,
            # "NEBULA_HOST": Config.NEBULA_HOST
            # 暂时注释掉 NEBULA 检查，如果还没配好可以先跑通 MinIO
        }
        for name, value in required_keys.items():
            if not value:
                raise ValueError(f"❌ 关键配置缺失: {name}。请检查 .env 文件。")
        print(f"✅ 配置文件校验通过，准备启动 {Config.SERVICE_NAME}...")

# 执行校验
Config.validate()