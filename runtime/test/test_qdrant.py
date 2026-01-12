# runtime/inspect_qdrant.py
from qdrant_client import QdrantClient
import json

client = QdrantClient(host="127.0.0.1", port=26333)
collection_name = "chimera_docs"

# 1. 检查总数
count = client.count(collection_name=collection_name)
print(f"📊 总分片数: {count}")

# 2. 检查最近的 3 条数据
points = client.scroll(collection_name=collection_name, limit=3)[0]
for p in points:
    print(f"--- Point ID: {p.id} ---")
    print(f"KB_ID: {p.payload.get('kb_id')}")
    print(f"Status: {p.payload.get('kg_status')}")
    print(f"Content: {p.payload.get('content')[:50]}...")