import io
from minio import Minio
from opentelemetry import trace
from config import Config

tracer = trace.get_tracer(__name__)

class MinioStore:
    def __init__(self):
        self.client = Minio(
            Config.MINIO_ENDPOINT,
            access_key=Config.MINIO_ACCESS_KEY,
            secret_key=Config.MINIO_SECRET_KEY,
            secure=False # 本地开发通常是 http
        )
        # 🔥 修改：使用 Config 中的桶名，或者默认为 chimera-docs (与 Go 保持一致)
        self.bucket = getattr(Config, "MINIO_BUCKET", "chimera-docs")

    def download_file(self, storage_path: str) -> bytes:
        """
        从 MinIO 下载文件并记录 Trace
        """
        with tracer.start_as_current_span("Skill:Minio_Download") as span:
            span.set_attribute("minio.path", storage_path)
            try:
                # 这里的 bucket 必须和 Go 上传时的 bucket 一致
                response = self.client.get_object(self.bucket, storage_path)
                data = response.read()
                span.set_attribute("file.size", len(data))
                return data
            except Exception as e:
                span.record_exception(e)
                raise Exception(f"MinIO 下载失败: {str(e)} (Bucket: {self.bucket}, Path: {storage_path})")
            finally:
                if 'response' in locals():
                    response.close()
                    response.release_conn()