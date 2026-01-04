import logging
import io
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

# Docling 核心组件
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.document import DocumentStream
from docling.chunking import HybridChunker

# 🔥 核心修正：仅引入 Label，不再尝试引入不存在的 HeadingItem
from docling_core.types.doc import DocItemLabel

class DoclingParser:
    _converter = None
    _chunker = None

    @classmethod
    def _get_components(cls):
        """单例模式初始化"""
        if cls._converter is None:
            logging.info("🐢 [Init] 初始化 Docling v2 层次化引擎...")
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            pipeline_options.do_table_structure = True

            cls._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )

            # 调低 max_tokens 解决上一步提到的 (531 > 512) 警告
            cls._chunker = HybridChunker(
                tokenizer="sentence-transformers/all-MiniLM-L6-v2",
                max_tokens=400,
                merge_peers=True,
            )
            logging.info("✅ [Init] Docling 引擎就绪")
        return cls._converter, cls._chunker

    @staticmethod
    def _get_header_path(item, doc) -> List[str]:
        """
        Docling v2 兼容逻辑：利用 label 判断标题并溯源
        """
        path = []
        try:
            curr = item
            # v2 中父节点引用通常在 item.parent 中
            while curr and hasattr(curr, "parent") and curr.parent is not None:
                # 使用 doc[index] 或 doc.get_item 访问父节点
                # 注意：在某些版本中 doc[curr.parent] 是标准写法
                parent_item = doc[curr.parent]

                # 🔥 使用 label 进行类型判断
                if parent_item.label == DocItemLabel.HEADING:
                    path.insert(0, parent_item.text.strip())
                curr = parent_item
        except Exception as e:
            # 溯源异常通常是因为到达了根节点或结构断裂，静默处理
            pass
        return path

    @staticmethod
    def _table_to_propositions(table_item, doc) -> str:
        """
        表格命题化实现 (Task 1.3)
        """
        try:
            df = table_item.export_to_dataframe(doc)
            if df is None or df.empty:
                return ""

            propositions = []
            table_title = "数据表"
            if hasattr(table_item, 'caption') and table_item.caption:
                table_title = table_item.caption.text.strip()

            for idx, row in df.iterrows():
                row_header = f"第{idx+1}行"
                for col in df.columns:
                    val = row[col]
                    if pd.isna(val) or str(val).strip() == "":
                        continue
                    # 构造陈述句增强语义搜索
                    prop = f"在《{table_title}》中，{row_header}的“{col}”是“{val}”。"
                    propositions.append(prop)

            return "\n".join(propositions)
        except Exception as e:
            logging.warning(f"⚠️ 表格处理跳过: {e}")
            return ""

    @staticmethod
    def parse_and_chunk(file_source, filename="temp.pdf") -> List[Dict[str, Any]]:
        converter, chunker = DoclingParser._get_components()
        logging.info(f"📄 [Docling] 正在解析: {filename}")

        try:
            if isinstance(file_source, bytes):
                input_doc = DocumentStream(name=filename, stream=io.BytesIO(file_source))
            else:
                input_doc = Path(file_source)

            conv_result = converter.convert(input_doc)
            doc = conv_result.document # v2 DoclingDocument 对象

            # 执行切分
            chunk_iter = chunker.chunk(doc)

            final_chunks = []
            for i, chunk in enumerate(chunk_iter):
                header_path = []
                page_num = 1
                processed_content = chunk.text

                # 溯源层级与表格逻辑
                if chunk.meta.doc_items:
                    first_item = chunk.meta.doc_items[0]

                    # 1. 提取面包屑路径
                    header_path = DoclingParser._get_header_path(first_item, doc)

                    # 2. 提取页码
                    if hasattr(first_item, 'prov') and first_item.prov:
                        page_num = first_item.prov[0].page_no

                    # 3. 如果是表格，应用命题化转换
                    if first_item.label == DocItemLabel.TABLE:
                        table_props = DoclingParser._table_to_propositions(first_item, doc)
                        if table_props:
                            processed_content = table_props

                breadcrumb = " > ".join(header_path)
                # 融合 Tree-T 结构与正文
                enriched_content = f"【位置: {breadcrumb}】\n{processed_content}" if breadcrumb else processed_content

                final_chunks.append({
                    "content": enriched_content,
                    "metadata": {
                        "header_path": header_path,
                        "breadcrumb": breadcrumb,
                        "level": len(header_path),
                        "page_number": page_num,
                        "file_name": filename
                    }
                })

            logging.info(f"✂️ [Tree-T] 已生成 {len(final_chunks)} 个高质量切片")
            return final_chunks

        except Exception as e:
            logging.error(f"❌ [Docling] 解析崩溃: {e}", exc_info=True)
            return []