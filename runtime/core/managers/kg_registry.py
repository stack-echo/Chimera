import sys

class KGRegistry:
    """
    使用 sys.modules 确保在任何导入方式下都指向同一个字典
    """
    @classmethod
    def _get_storage(cls):
        if not hasattr(sys, "_chimera_kg_agents"):
            sys._chimera_kg_agents = {}
        return sys._chimera_kg_agents

    @classmethod
    def register(cls, name, agent_instance):
        storage = cls._get_storage()
        storage[name] = agent_instance
        print(f"🔓 [Registry] Agent '{name}' registered in global storage.")

    @classmethod
    def get_agent(cls, name):
        return cls._get_storage().get(name)

    @classmethod
    def is_active(cls):
        return "extractor" in cls._get_storage()