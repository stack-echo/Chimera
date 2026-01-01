import logging
import time
from typing import List, Dict, Any
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig
from config import Config

logger = logging.getLogger(__name__)

class NebulaStore:
    def __init__(self, cfg):
        self.space = cfg.NEBULA_SPACE
        self.user = cfg.NEBULA_USER
        self.pwd = cfg.NEBULA_PASSWORD

        config = NebulaConfig()
        config.max_connection_pool_size = 10
        # 增加超时设置
        config.timeout = 30000
        self.pool = ConnectionPool()

        if not self.pool.init([(cfg.NEBULA_HOST, cfg.NEBULA_PORT)], config):
            raise Exception("❌ Failed to connect to NebulaGraph")

        self._ensure_schema()

    def execute(self, nql: str):
        """执行原生 nGQL"""
        with self.pool.session_context(self.user, self.pwd) as session:
            # 即使我们用了显式空间名，USE 一下也是个好习惯，作为双重保险
            session.execute(f"USE {self.space};")
            result = session.execute(nql)
            if not result.is_succeeded():
                logger.error(f"nGQL Exec Error: {result.error_msg()} | Query: {nql[:100]}...")
            return result

    def _ensure_schema(self):
        """定义数据模型"""
        logger.info(f"🛠️ [Nebula] 正在检查图空间: {self.space}")
        with self.pool.session_context(self.user, self.pwd) as session:
            session.execute(f"CREATE SPACE IF NOT EXISTS {self.space} (partition_num=10, replica_factor=1, vid_type=FIXED_STRING(64));")
            time.sleep(3)

            session.execute(f"USE {self.space};")
            ddl_list = [
                "CREATE TAG IF NOT EXISTS Entity(name string, type string, description string);",
                "CREATE TAG IF NOT EXISTS Chunk(source_id int, kb_id int);",
                "CREATE EDGE IF NOT EXISTS RELATION(description string, weight double);",
                "CREATE EDGE IF NOT EXISTS MENTIONED_IN(score double);"
            ]
            for ddl in ddl_list:
                session.execute(ddl)
            time.sleep(2)

    def upsert_entities(self, entities: List[Dict]):
        if not entities: return
        values = []
        for e in entities:
            vid = self._escape(e["vid"])
            name = self._escape(e["props"].get("name", ""))
            typ = self._escape(e["props"].get("type", "Unknown"))
            desc = self._escape(e["props"].get("desc", ""))
            values.append(f'"{vid}":("{name}", "{typ}", "{desc}")')

        # 🔥 修改：显式指定空间名 {self.space}.Entity
        nql = f'INSERT VERTEX {self.space}.Entity(name, type, description) VALUES {", ".join(values)};'
        self.execute(nql)

    def upsert_relations(self, relations: List[Dict]):
        if not relations: return
        values = []
        for r in relations:
            src = self._escape(r["src"])
            dst = self._escape(r["dst"])
            desc = self._escape(r["props"].get("desc", ""))
            weight = r["props"].get("weight", 1.0)
            values.append(f'"{src}"->"{dst}"@0:("{desc}", {weight})')

        # 🔥 修改：显式指定空间名 {self.space}.RELATION
        nql = f'INSERT EDGE {self.space}.RELATION(description, weight) VALUES {", ".join(values)};'
        self.execute(nql)

    def upsert_chunk_link(self, chunk_id: str, entities: List[str], meta: Dict):
        chunk_vid = self._escape(chunk_id)
        source_id = meta.get("source_id", 0) or 0
        kb_id = meta.get("kb_id", 0) or 0

        # 🔥 修改：显式指定空间名
        nql_v = f'INSERT VERTEX {self.space}.Chunk(source_id, kb_id) VALUES "{chunk_vid}":({source_id}, {kb_id});'
        self.execute(nql_v)

        if not entities: return
        edge_values = []
        for ent_vid in entities:
            clean_vid = self._escape(ent_vid)
            edge_values.append(f'"{clean_vid}"->"{chunk_vid}"@0:(1.0)')

        # 🔥 修改：显式指定空间名
        nql_e = f'INSERT EDGE {self.space}.MENTIONED_IN(score) VALUES {", ".join(edge_values)};'
        self.execute(nql_e)

    def _escape(self, text: str) -> str:
        if not isinstance(text, str): return str(text)
        # 简单转义双引号和反斜杠
        return text.replace('\\', '\\\\').replace('"', '\\"')

    def retrieve_subgraph(self, entities: List[str], depth: int = 1) -> List[str]:
        """
        🔥 核心：根据实体名召回子图
        返回格式化的三元组字符串列表: ["DeepSeek --(developed_by)--> High-Flyer", ...]
        """
        if not entities:
            return []

        # 构造 IN 查询列表
        names_str = ", ".join([f'"{self._escape(e)}"' for e in entities])

        # nGQL: 查找这些点出发或到达的关系
        # MATCH (v:Entity)-[e:RELATION]-(v2) WHERE v.Entity.name IN ["A", "B"] RETURN ...
        nql = f'''
        USE {self.space};
        MATCH (v:Entity)-[e:RELATION]-(v2)
        WHERE v.Entity.name IN [{names_str}]
        RETURN v.Entity.name AS src, e.description AS rel, v2.Entity.name AS dst
        LIMIT 30;
        '''

        try:
            result = self.execute(nql)
            if not result.is_succeeded() or result.is_empty():
                return []

            triplets = []
            # 解析结果集
            # Nebula Python Client 的结果遍历比较特殊
            for row in result.rows():
                # 假设列顺序是 src, rel, dst
                # row.values[0] 是 ValueWrapper，需要 cast
                src = row.values[0].get_sVal().decode('utf-8')
                rel = row.values[1].get_sVal().decode('utf-8')
                dst = row.values[2].get_sVal().decode('utf-8')

                triplets.append(f"{src} --({rel})--> {dst}")

            return triplets

        except Exception as e:
            logger.error(f"Subgraph Retrieval Error: {e}")
            return []