import logging
import io
from pathlib import Path

# Docling 核心组件
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.document import DocumentStream

# 🔥 关键：HybridChunker 在 docling.chunking 下
from docling.chunking import HybridChunker

class DoclingParser:
    _converter = None
    _chunker = None
    def __init__(self):
        # 预加载模型，避免在请求中初始化
        self.converter = DocumentConverter()

    @classmethod
    def _get_components(cls):
        """单例模式初始化 Converter 和 Chunker"""
        if cls._converter is None:
            logging.info("🐢 [Init] 正在初始化 Docling 模型 (HybridChunker enabled)...")

            # 1. 配置转换器
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            pipeline_options.do_table_structure = True

            cls._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )

            # 2. 配置切分器 (HybridChunker)
            # 使用 sentence-transformers 的 tokenizer 来计算 token 数，确保切片不会超长
            cls._chunker = HybridChunker(
                tokenizer="sentence-transformers/all-MiniLM-L6-v2",
                max_tokens=500, # 适合 embedding 模型的窗口大小
                merge_peers=True,
            )

            logging.info("✅ [Init] Docling 组件就绪")
        return cls._converter, cls._chunker

    @staticmethod
    def parse_and_chunk(file_source, filename="temp.pdf"):
        """
        解析 PDF 并返回带有【真实页码】的语义切片
        :param file_source: 可以是 str (路径), Path (路径), 或 bytes (二进制)
        """
        converter, chunker = DoclingParser._get_components()
        logging.info(f"📄 [Docling] 开始解析: {filename}")

        try:
            # 1. 智能构建输入源
            input_doc = None

            if isinstance(file_source, bytes):
                # Case A: 传入二进制流 (内存处理)
                logging.info(f"   ⚙️ Mode: Bytes Stream ({len(file_source)} bytes)")
                input_doc = DocumentStream(name=filename, stream=io.BytesIO(file_source))
            elif isinstance(file_source, (str, Path)):
                # Case B: 传入文件路径 (推荐，性能更好且稳定)
                logging.info(f"   ⚙️ Mode: File Path ({file_source})")
                input_doc = Path(file_source)
            else:
                raise ValueError(f"不支持的输入类型: {type(file_source)}")

            # 2. 执行转换 (PDF -> DL Document)
            conv_result = converter.convert(input_doc)
            doc = conv_result.document
            logging.info(f"✅ [Docling] 转换完成，开始 HybridChunker 切分...")

            # 3. 使用 HybridChunker 切分
            chunk_iter = chunker.chunk(doc)

            final_chunks = []
            for i, chunk in enumerate(chunk_iter):
                # 🔥 提取页码 (追溯 Provenance)
                page_num = 1
                if chunk.meta.doc_items:
                    first_item = chunk.meta.doc_items[0]
                    if hasattr(first_item, 'prov') and first_item.prov:
                        page_num = first_item.prov[0].page_no

                # 序列化结果
                # chunk.text 已经包含了上下文（如标题）
                final_chunks.append({
                    "content": chunk.text,
                    "page": page_num
                })

            logging.info(f"✂️ [HybridChunker] 生成了 {len(final_chunks)} 个带有页码的片段")

            return final_chunks

        except Exception as e:
            logging.error(f"❌ [Docling] 解析失败: {e}", exc_info=True)
            return []