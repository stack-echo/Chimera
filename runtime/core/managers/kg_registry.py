from typing import Dict, Any, Optional

class KGRegistry:
    _agents: Dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, agent_instance: Any):
        cls._agents[name] = agent_instance
        print(f"🔓 [Registry] Agent '{name}' registered.")

    @classmethod
    def get_agent(cls, name: str) -> Optional[Any]:
        return cls._agents.get(name)

    @classmethod
    def is_active(cls) -> bool:
        # 如果注册了核心抽取器，则认为图谱流水线已激活
        return "extractor" in cls._agents