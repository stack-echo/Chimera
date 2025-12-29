from config import Config
from langchain_text_splitters import MarkdownHeaderTextSplitter

class TextSplitter:
    @staticmethod
    def sliding_window(text: str):
        """
        基础的滑动窗口切分算法
        Args:
            text: 原始文本
        Returns:
            List[str]: 切分后的文本块列表
        """
        chunks = []
        start = 0
        text_len = len(text)

        # 防止死循环或空文本
        if text_len == 0:
            return []

        while start < text_len:
            end = start + Config.CHUNK_SIZE
            # 截取片段
            segment = text[start:end]
            chunks.append(segment)

            # 如果剩下的文本不足以构成重叠，直接结束
            if end >= text_len:
                break

            # 滑动指针
            start += (Config.CHUNK_SIZE - Config.CHUNK_OVERLAP)

        return chunks

    @staticmethod
    def markdown_split(markdown_text: str):
        """
        🔥 v0.3.0 核心：基于 Markdown 标题的语义切分
        """
        # 定义要切分的标题级别 (H1, H2, H3)
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]

        # 初始化 LangChain 切分器
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False # 建议保留标题在正文中，上下文更完整
        )

        # 执行切分
        docs = splitter.split_text(markdown_text)

        final_chunks = []
        for doc in docs:
            # doc.page_content 是正文
            # doc.metadata 包含标题路径 {'Header 1': '...', 'Header 2': '...'}

            # 💡 核心技巧：将标题路径拼回到内容前面
            # 这样 LLM 就算只看到这一段，也知道它属于 "第一章 > 背景介绍"
            header_path = " > ".join(doc.metadata.values())
            if header_path:
                content = f"【章节: {header_path}】\n{doc.page_content}"
            else:
                content = doc.page_content

            final_chunks.append(content)

        return final_chunks