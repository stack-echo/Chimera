import os
import logging
import importlib
import pkgutil

logger = logging.getLogger(__name__)

def load_enterprise_plugins():
    """
    自动扫描并加载 enterprise 目录下的扩展模块。
    返回: bool (是否加载了企业版组件)
    """
    # 获取当前文件所在目录 (runtime/)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    enterprise_dir = os.path.join(base_dir, "enterprise")

    # 1. 检查目录是否存在
    if not os.path.exists(enterprise_dir):
        logger.info("ℹ️ [Loader] No 'enterprise' directory found. Running in Community Edition.")
        return False

    # 确保 runtime 目录在 sys.path 中，以便可以 import enterprise...
    # (通常运行 main.py 时已经在路径中了，这里是双重保险)

    loaded_any = False

    # 2. 扫描并加载连接器 (Connectors)
    # 目标路径: runtime/enterprise/core/connectors/
    connectors_path = os.path.join(enterprise_dir, "core", "connectors")
    if os.path.exists(connectors_path):
        # 使用 pkgutil 遍历目录下的所有 .py 文件
        for _, name, _ in pkgutil.iter_modules([connectors_path]):
            if name == "__init__": continue

            module_name = f"enterprise.core.connectors.{name}"
            try:
                importlib.import_module(module_name)
                logger.info(f"🔓 [Loader] Activated Enterprise Connector: {name}")
                loaded_any = True
            except Exception as e:
                logger.warning(f"⚠️ [Loader] Failed to load connector '{name}': {e}")

    # 3. 这里可以扩展加载其他组件 (如 Workflows, Tools)

    if loaded_any:
        logger.info("✅ Enterprise environment initialized.")
    else:
        logger.info("ℹ️ Enterprise directory exists but no plugins loaded.")

    return True