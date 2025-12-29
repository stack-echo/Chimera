from sentence_transformers import SentenceTransformer
from config import Config
import logging

class EmbeddingModel:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            logging.info("📥 Loading Embedding Model...")
            try:
                # 生产环境可以用 modelscope 的 snapshot_download
                cls._instance = SentenceTransformer(Config.EMBEDDING_MODEL_NAME)
            except:
                cls._instance = SentenceTransformer('all-MiniLM-L6-v2')
            logging.info("✅ Embedding Model Loaded")
        return cls._instance

    @staticmethod
    def encode(text: str):
        model = EmbeddingModel.get_instance()
        return model.encode(text).tolist()