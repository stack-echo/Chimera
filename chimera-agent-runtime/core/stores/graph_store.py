from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig

class NebulaStore:
    def __init__(self, cfg):
        config = NebulaConfig()
        config.max_connection_pool_size = 10
        self.pool = ConnectionPool()

        # 🔥 修复：保存用户名和密码供 session_context 使用
        self.user = cfg.NEBULA_USER
        self.pwd = cfg.NEBULA_PASSWORD

        if not self.pool.init([(cfg.NEBULA_HOST, cfg.NEBULA_PORT)], config):
            raise Exception("Failed to connect to NebulaGraph")

    def execute(self, space, nql):
        """执行 nGQL 语句"""
        # 这里需要 self.user 和 self.pwd
        with self.pool.session_context(self.user, self.pwd) as session:
            session.execute(f"USE {space};")
            return session.execute(nql)