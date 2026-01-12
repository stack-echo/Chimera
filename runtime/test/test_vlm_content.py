# runtime/debug_vlm_content.py
from qdrant_client import QdrantClient

client = QdrantClient(host="127.0.0.1", port=26333, check_compatibility=False)
# 搜索包含“图片”关键字的 Payload
results = client.scroll(
    collection_name="chimera_docs",
    scroll_filter={"must": [{"key": "content", "match": {"text": "图片"}}]},
    limit=5
)[0]

for r in results:
    print(f"ID: {r.id}")
    print(f"Content: {r.payload['content'][:300]}")
    print("-" * 50)