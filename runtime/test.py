# runtime/nebula_test.py
from config import Config
from enterprise.core.stores.graph_store import NebulaStore
import logging

logging.basicConfig(level=logging.INFO)

try:
    print(f"尝试连接: {Config.NEBULA_HOST}:{Config.NEBULA_PORT}")
    store = NebulaStore(Config)
    print("🚀 恭喜！连接完全成功！")
except Exception as e:
    print(f"❌ 连接失败，原因为: {e}")