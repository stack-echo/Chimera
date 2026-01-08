from typing import List
import logging
from agents.base import BaseAgent
from core.telemetry.tracing import trace_agent

logger = logging.getLogger(__name__)

class QueryAnalysisAgent(BaseAgent):
    def __init__(self):
        # 1. 指向专用的意图分析提示词
        super().__init__(agent_id="Query_Analysis_Expert", prompt_file="chat/query_analysis.yaml")

    @trace_agent(agent_name="Query_Analysis_Expert")
    def run(self, query: str) -> List[str]:
        result = self.ask_llm(input_vars={"text": query}, response_format="json")

        if isinstance(result, dict) and "entities" in result:
            return result["entities"]
        return [query]