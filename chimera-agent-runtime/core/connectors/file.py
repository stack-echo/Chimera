import os
import logging
from .base import BaseConnector, DocumentChunk
from tools.doc_parser import DoclingParser # 复用你之前的工具
from core.stores.minio_store import MinioStore # 复用你之前的 MinIO 工具

logger = logging.getLogger(__name__)

class FileConnector(BaseConnector):
    def __init__(self, kb_id, source_id, config):
        super().__init__(kb_id, source_id, config)
        # config 示例: {"storage_path": "kbs/1/xxx.pdf", "file_name": "manual.pdf"}
        self.storage_path = config.get("storage_path")
        self.file_name = config.get("file_name", "unknown.pdf")
        self.minio = MinioStore() # 假设该类已初始化好配置

    def load(self):
        """
        流程: MinIO下载 -> 临时文件 -> Docling解析 -> Yield Chunk
        """
        temp_path = f"/tmp/{self.file_name}"

        try:
            # 1. 从 MinIO 下载文件到本地临时目录
            logger.info(f"📥 下载文件: {self.storage_path}")
            data_bytes = self.minio.download_file(self.storage_path)

            # Docling 目前对路径支持最好，所以先存临时文件
            with open(temp_path, "wb") as f:
                f.write(data_bytes)

            # 2. 调用 Docling 解析
            # parse_and_chunk 返回 [{"content": "...", "page": 1}, ...]
            chunks = DoclingParser.parse_and_chunk(temp_path, self.file_name)

            # 3. 转换为标准 DocumentChunk 并 Yield
            for chunk in chunks:
                yield DocumentChunk(
                    content=chunk["content"],
                    metadata={
                        "page_number": chunk["page"],
                        "file_name": self.file_name,
                        "file_path": self.storage_path
                    }
                )

        except Exception as e:
            logger.error(f"FileConnector Error: {e}")
            raise e
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)