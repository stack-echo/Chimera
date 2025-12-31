import logging
import requests
import json
from typing import Iterator
from .base import BaseConnector, DocumentChunk
from config import Config

logger = logging.getLogger(__name__)

class FeishuConnector(BaseConnector):
    """
    飞书知识库连接器
    配置要求: {"app_id": "...", "app_secret": "...", "wiki_space_id": "..."}
    """
    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, kb_id, source_id, config):
        super().__init__(kb_id, source_id, config)
        self.app_id = config.get("app_id")
        self.app_secret = config.get("app_secret")
        self.space_id = config.get("wiki_space_id") # 知识库空间ID

    def _get_tenant_token(self):
        """获取租户访问凭证 (Tenant Access Token)"""
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return resp.json().get("tenant_access_token")

    def _list_nodes(self, token):
        """获取知识库所有节点 (文档列表)"""
        # 注意: 实际需处理分页 (page_token)，这里演示简化版只取第一页
        url = f"{self.BASE_URL}/wiki/v2/spaces/{self.space_id}/nodes"
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            logger.error(f"Feishu List Nodes Failed: {resp.text}")
            return []

        data = resp.json().get("data", {})
        return data.get("items", [])

    def _get_doc_content(self, token, obj_token, doc_type):
        """获取文档纯文本内容"""
        # 飞书不同类型的文档 API 不同，这里以 docx 为例
        # 实际上你可能需要调用 "获取文档纯文本" 接口，或者 "导出接口"
        # 简单方案：使用 docx/v1/documents/{document_id}/raw_content

        # 注意：Wiki 节点的 obj_token 还需要转换成 document_id，或者直接尝试读取
        # 这里为了演示，我们假设它是一个 docx
        if doc_type != "docx":
            return f"[暂不支持的文档类型: {doc_type}]"

        url = f"{self.BASE_URL}/docx/v1/documents/{obj_token}/raw_content"
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            logger.warning(f"Fetch content failed for {obj_token}: {resp.text}")
            return ""

        return resp.json().get("data", {}).get("content", "")

    def load(self) -> Iterator[DocumentChunk]:
        logger.info(f"📚 [Feishu] 开始同步空间: {self.space_id}")

        try:
            # 1. 鉴权
            token = self._get_tenant_token()

            # 2. 遍历节点
            nodes = self._list_nodes(token)
            logger.info(f"📚 [Feishu] 发现 {len(nodes)} 个节点")

            for node in nodes:
                title = node.get("title", "无标题")
                obj_token = node.get("obj_token")
                obj_type = node.get("obj_type") # doc, docx, sheet...

                # 3. 获取内容
                content = self._get_doc_content(token, obj_token, obj_type)

                if not content or len(content) < 10:
                    continue

                # 4. 简单切分 (生产环境应用 TextSplitter)
                # 这里我们假设每篇文档作为一个大块返回，或者按换行符切
                # 为了复用 Qdrant 逻辑，我们这里做简单的长度切分
                chunk_size = 500
                for i in range(0, len(content), chunk_size):
                    segment = content[i : i + chunk_size]

                    yield DocumentChunk(
                        content=segment,
                        metadata={
                            "source": "feishu",
                            "doc_id": obj_token,
                            "title": title,
                            "url": f"https://feishu.cn/wiki/{obj_token}", # 溯源链接
                            "page_number": 1
                        }
                    )

        except Exception as e:
            logger.error(f"Feishu Sync Error: {e}")
            raise e