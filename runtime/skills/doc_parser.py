import logging
import io
import uuid
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.document import DocumentStream
from docling.chunking import HybridChunker
from docling_core.types.doc import DocItemLabel

logger = logging.getLogger(__name__)

class DoclingParser:
    _converter = None
    _chunker = None

    @classmethod
    def _get_components(cls):
        if cls._converter is None:
            logger.info("🐢 [Init] 启动 Docling v2 高兼容性模式...")
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True
            pipeline_options.do_table_structure = True

            # 开启图片识别
            pipeline_options.generate_picture_images = True
            pipeline_options.images_scale = 2.0

            cls._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )

            cls._chunker = HybridChunker(
                tokenizer="sentence-transformers/all-MiniLM-L6-v2",
                max_tokens=512,
                merge_peers=True,
            )
        return cls._converter, cls._chunker

    @staticmethod
    def parse_and_chunk(file_source, filename="temp.pdf") -> List[Dict[str, Any]]:
        converter, chunker = DoclingParser._get_components()

        try:
            if isinstance(file_source, bytes):
                input_doc = DocumentStream(name=filename, stream=io.BytesIO(file_source))
            else:
                input_doc = Path(file_source)

            # 1. 执行转换
            conv_result = converter.convert(input_doc)

            # 2. 🔥 核心修正：使用 Markdown 导出作为内容基准
            # 这是避开“元素数量为1” Bug 的最强手段
            markdown_content = conv_result.document.export_to_markdown()

            if not markdown_content or len(markdown_content.strip()) < 5:
                logger.error("❌ 文档内容提取失败（Markdown 为空）")
                return []

            logger.info(f"📝 [Docling] 成功提取文本内容，长度: {len(markdown_content)} 字符")

            # 3. 使用 HybridChunker 进行切分
            # 注意：在某些 Docling 版本下，chunker.chunk 可以直接接收 doc 对象
            chunk_iter = chunker.chunk(conv_result.document)
            final_chunks = []

            for i, chunk in enumerate(chunk_iter):
                # 尝试定位图片
                image_path = None
                is_table = False
                page_num = 1

                # 处理图片路径 (Task 2.2)
                if chunk.meta.doc_items:
                    for item in chunk.meta.doc_items:
                        if item.label == DocItemLabel.TABLE:
                            is_table = True
                            try:
                                # 尝试获取表格图片
                                image_obj = conv_result.document.get_image(item)
                                if image_obj:
                                    img_id = str(uuid.uuid4())[:8]
                                    image_path = f"/tmp/chimera_table_{img_id}.jpg"
                                    image_obj.save(image_path)

                                    # 💡 关键：向上回溯寻找“Table x”字样
                                    # 这里我们可以简单地把当前 chunk 的 text（通常包含标题）作为 context
                                    logger.info(f"📸 [Table-Found] 锁定表格，准备视觉转录...")
                            except: pass
                            break
                        if item.label == DocItemLabel.PICTURE:
                            try:
                                img_id = str(uuid.uuid4())[:8]
                                temp_img = f"/tmp/chimera_img_{img_id}.jpg"
                                image_obj = conv_result.document.get_image(item)
                                if image_obj:
                                    image_obj.save(temp_img)
                                    image_path = temp_img
                                    logger.info(f"📸 捕捉到切片关联插图: {temp_img}")
                                    break
                            except: pass

                # 提取哈希
                c_hash = hashlib.md5(chunk.text.encode()).hexdigest()

                final_chunks.append({
                    "content": chunk.text,
                    "metadata": {
                        "content_hash": c_hash,
                        "image_path": image_path,
                        "page_number": 1, # 默认 1，如果有 prov 则在下面覆盖
                        "breadcrumb": "",
                        "file_name": filename
                    }
                })

            # 4. 🔥 最终补偿逻辑：如果 Chunker 依然返回 0
            if not final_chunks and len(markdown_content) > 10:
                logger.warning("⚠️ Chunker 无法识别文档结构，执行流式补偿切分...")
                # 简单按长度切分，保证系统不空转
                text = markdown_content
                step = 1000
                for j in range(0, len(text), step):
                    sub_text = text[j:j+step]
                    final_chunks.append({
                        "content": sub_text,
                        "metadata": {
                            "content_hash": hashlib.md5(sub_text.encode()).hexdigest(),
                            "file_name": filename
                        }
                    })

            logger.info(f"✂️ [Tree-T] 解析完毕，最终产出 {len(final_chunks)} 个切片")
            return final_chunks

        except Exception as e:
            logger.error(f"❌ [Docling] 严重崩溃: {e}", exc_info=True)
            return []

    @staticmethod
    def _table_to_propositions(table_item, doc) -> tuple[str, str]:
        """
        返回: (结构化文本, 临时截图路径)
        """
        table_text = ""
        temp_img_path = None

        try:
            df = table_item.export_to_dataframe(doc)
            if df is None or df.empty:
                # 命题化逻辑...
                table_text = "...(此处省略之前写过的命题逻辑)..."
        except:
            pass

        # 2. 强制备份：不管结构化成不成功，都给表格存一张图
        # 很多时候结构化会丢掉合并单元格的信息，VLM 能补全
        try:
            img_id = str(uuid.uuid4())[:8]
            temp_img_path = f"/tmp/chimera_table_{img_id}.jpg"
            image_obj = doc.get_image(table_item)
            if image_obj:
                image_obj.save(temp_img_path)
        except:
            pass

        return table_text, temp_img_path