import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 服务配置
    PORT = 50051
    MAX_MESSAGE_LENGTH = 100 * 1024 * 1024

    # 模型配置
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    EMBEDDING_MODEL_NAME = 'AI-ModelScope/all-MiniLM-L6-v2'

    # 业务参数
    CHUNK_SIZE = 500  # 增大一点，适配 Docling 的段落感
    CHUNK_OVERLAP = 50

    @staticmethod
    def validate():
        if not Config.DEEPSEEK_API_KEY:
            raise ValueError("❌ 未配置 DEEPSEEK_API_KEY")

Config.validate()