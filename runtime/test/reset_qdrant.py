from qdrant_client import QdrantClient

client = QdrantClient(host="127.0.0.1", port=26333)
collection_name = "chimera_docs"

print(f"🧹 正在清理集合: {collection_name}")
client.delete_collection(collection_name=collection_name)
print("✅ 清理完成，现在系统将从零开始构建纯净的知识库。")