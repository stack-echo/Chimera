import time
import json
import logging
import redis
from config import Config
from core.stores.qdrant_store import QdrantStore
from core.managers.etl_manager import ETLManager
from loader import load_enterprise_plugins
import core.connectors.file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ETL-Worker")

def run_worker():
    # 1. 加载企业插件 (确保图谱能力被激活)
    load_enterprise_plugins()

    # 2. 初始化核心组件
    qdrant = QdrantStore()
    # 尝试连接 Nebula
    nebula = None
    if getattr(Config, "NEBULA_HOST", None):
        try:
            from enterprise.core.stores.graph_store import NebulaStore
            nebula = NebulaStore(Config)
        except:
            logger.warning("Worker running without Nebula support")

    etl_mgr = ETLManager(qdrant, nebula)

    # 3. 连接 Redis
    r = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, password=getattr(Config, "REDIS_PASSWORD", None))
    try:
        r.ping()
        logger.info(f"✅ Successful connection to Redis at {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        return
    queue_name = "chimera_etl_tasks"

    try:
        # 强制在这里初始化 VLM，如果显存不够，这里会直接报错
        from skills.vlm_service import VLMService
        _ = VLMService.get_instance()
        logger.info("🎨 VLM 视觉引擎已就绪")
    except Exception as e:
        logger.error(f"❌ VLM 初始化失败，Worker 停止: {e}")
        return # 👈 关键：失败就停止，不要空转

    logger.info(f"🔥 ETL Worker is ready, listening on queue: {queue_name}")

    while True:
        try:
            # 4. 阻塞式弹出任务 (BLPOP)
            _, task_json = r.blpop(queue_name)
            task = json.loads(task_json)

            ds_id = task['ds_id']
            logger.info(f"🚀 [Worker] Received task for DS:{ds_id}")

            # 5. 执行同步任务 (Manager 现在是生成器)
            iterator = etl_mgr.sync_datasource(
                kb_id=task['kb_id'],
                source_id=ds_id,
                source_type=task['type'],
                config_json=task['config_json']
            )

            # 消费生成器，执行同步
            for progress in iterator:
                # 后续可在此更新任务进度到 Redis
                pass

            logger.info(f"✅ [Worker] Task completed for DS:{ds_id}")

        except Exception as e:
            logger.error(f"❌ [Worker] Error processing task: {e}")
            time.sleep(2)

if __name__ == "__main__":
    run_worker()