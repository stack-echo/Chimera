# runtime/test.py
import logging
from loader import load_enterprise_plugins
from core.managers.kg_registry import KGRegistry

# 配置日志查看输出
logging.basicConfig(level=logging.INFO)

print("--- 开始加载测试 ---")
load_enterprise_plugins()
print("--- 加载结束 ---")

print(f"Extractor Ready: {KGRegistry.get_agent('extractor') is not None}")
print(f"Inspector Ready: {KGRegistry.get_agent('inspector') is not None}")
print(f"Resolver Ready: {KGRegistry.get_agent('resolution') is not None}")