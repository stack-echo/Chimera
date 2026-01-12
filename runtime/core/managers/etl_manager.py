import json
import time
import uuid
import glob
import logging
import hashlib
import traceback
from typing import Generator, Dict, Any, List, Optional

from core.llm.embedding import EmbeddingModel
from core.stores.qdrant_store import QdrantStore
from core.managers.kg_registry import KGRegistry
from core.connectors.base import ConnectorFactory

logger = logging.getLogger(__name__)

class ETLManager:
    def __init__(self, qdrant_store: QdrantStore, nebula_store: Any = None):
        self.qdrant = qdrant_store
        self.nebula = nebula_store
        self.embed_model = EmbeddingModel.get_instance()

        self.use_kg = self.nebula is not None and KGRegistry.is_active()

    def __del__(self):
        import glob
        temp_files = glob.glob("/tmp/chimera_img_*") + glob.glob("/tmp/chimera_table_*")
        for f in temp_files:
            try: os.remove(f)
            except: pass
        logger.info("🧹 Temporary vision files cleaned up.")

    def sync_datasource(self, kb_id: int, source_id: int, source_type: str, config_json: str) -> Generator[Dict[str, Any], None, None]:
        """
        同步主任务：集成领域感知、异步批处理与状态自愈
        """
        start_time = time.time()
        logger.info(f"🔄 [ETL Start] KB={kb_id} Source={source_id} Type={source_type}")
        final_metrics = {
            "total_entities": 0,
            "linked_entities": 0,
            "visual_entities": 0,
            "total_chunks": 0
        }

        try:
            config = json.loads(config_json)
            connector_cls = ConnectorFactory.get_connector(source_type)
            connector = connector_cls(kb_id, source_id, config)

            # 缓冲区配置
            vector_buffer = []
            kg_batch_buffer = []
            V_BATCH_SIZE = 10
            K_BATCH_SIZE = 1 # 针对 A4000 的 VLM 稳定性，建议设为 1 或 2

            total_processed = 0
            doc_domain = "general"

            # 1. 领域感知：预读第一个分片
            classifier = KGRegistry.get_agent("classifier")
            chunks_iterator = connector.load()
            first_chunk = next(chunks_iterator, None)

            if first_chunk and classifier:
                classification = classifier.run(config.get("file_name", "Unknown"), first_chunk.content)
                doc_domain = classification.get("domain", "general")
                logger.info(f"🏷️  [Domain] 文档领域识别为: {doc_domain.upper()}")

            # 2. 处理第一个分片
            if first_chunk:
                self._process_single_chunk(first_chunk, kb_id, source_id, doc_domain, vector_buffer, kg_batch_buffer)

            # 3. 循环处理剩余分片
            for chunk in chunks_iterator:
                self._process_single_chunk(chunk, kb_id, source_id, doc_domain, vector_buffer, kg_batch_buffer)

                # 4. 刷新逻辑：向量优先原则 (防止图谱更新时 ID 不存在)
                if len(vector_buffer) >= V_BATCH_SIZE:
                    self.qdrant.upsert_chunks(vector_buffer)
                    vector_buffer = []

                if len(kg_batch_buffer) >= K_BATCH_SIZE:
                    # 在抽图谱前，强制排空当前的向量缓冲区
                    batch_metrics = self._flush_kg_batch(kg_batch_buffer, domain=doc_domain)
                    for k in final_metrics:
                        if k in batch_metrics: final_metrics[k] += batch_metrics[k]
                    kg_batch_buffer = []


                final_metrics["total_chunks"] += 1
                yield {"chunks": final_metrics["total_chunks"], "status": "processing"}

            # 5. 清理最后残留的缓冲区
            if vector_buffer:
                self.qdrant.upsert_chunks(vector_buffer)
            if kg_batch_buffer:
                self._flush_kg_batch(kg_batch_buffer, domain=doc_domain)

            logger.info(f"✅ [ETL Done] 共处理 {total_processed} 个切片，耗时 {time.time() - start_time:.2f}s")
            yield {"success": True, "chunks": total_processed, "metrics": final_metrics}

        except Exception as e:
            logger.error(f"❌ [ETL Error] {str(e)}")
            logger.error(traceback.format_exc())
            raise e
        finally:
            # 🔥 4.1 自动清理临时视觉文件
            for f in glob.glob("/tmp/chimera_img_*") + glob.glob("/tmp/chimera_table_*"):
                try: os.remove(f)
                except: pass

    def _process_single_chunk(self, chunk, kb_id, source_id, domain, v_buf, k_buf):
        """
        内部逻辑单元：负责单个切片的 VLM 增强、向量化和指纹校验
        """
        chunk_uuid = str(uuid.uuid4())
        content_hash = chunk.metadata.get("content_hash")
        is_table = chunk.metadata.get("is_table", False)
        image_path = chunk.metadata.get("image_path")

        text_to_encode = chunk.content

        # 1. 视觉增强 (VLM)
        # 如果是表格且有截图，或者是一个 PICTURE
        if (is_table or image_path) and self.use_kg:
            try:
                from skills.vlm_service import VLMService
                vlm = VLMService.get_instance()

                # 调用 VLM，如果是表格则开启 is_table 模式
                # 这里的 image_path 可能是 doc_parser 生成的表格截图
                v_desc = vlm.describe_image(
                    image_path,
                    context_breadcrumb=chunk.metadata.get("breadcrumb", ""),
                    is_table=is_table
                )

                # 执行视觉推理
                image_desc = vlm.describe_image(image_path, context_breadcrumb=breadcrumb)

                # 将视觉信息锚定到文本，确保“图片”本身能被搜索到
                text_to_encode = f"【文档图表详情】\n{v_desc}\n\n[检索锚点: {chunk.content}]"

                # 任务完成后立即清理临时图片文件，防止磁盘溢出
                if os.path.exists(image_path):
                    os.remove(image_path)
            except Exception as ve:
                logger.error(f"⚠️ VLM 解析失败: {ve}")

        # 2. 生成嵌入向量
        vector = self.embed_model.encode(text_to_encode)

        # 3. 装载向量缓冲区 (注意：此处已修复变量名)
        v_buf.append({
            "id": chunk_uuid,
            "vector": vector,
            "payload": {
                "content": text_to_encode,
                "kb_id": kb_id,
                "source_id": source_id,
                "content_hash": content_hash,
                "kg_status": "pending", # 初始状态为待定
                "domain": domain,
                **{k: v for k, v in chunk.metadata.items() if k != 'image_path'}
            }
        })

        # 4. 装载图谱缓冲区 (增量校验)
        if self.use_kg:
            if not self._check_kg_completed(content_hash):
                k_buf.append({
                    "id": chunk_uuid,
                    "text": text_to_encode,
                    "metadata": chunk.metadata
                })
            else:
                # 记录跳过日志，用于监控增量同步效率
                logger.info(f"⏭️  [KG-Skip] 内容指纹 {content_hash[:8]} 已存在，跳过 LLM 抽取。")

    def _check_kg_completed(self, content_hash):
        if not content_hash: return False
        try:
            from qdrant_client.http import models
            res = self.client.scroll(
                collection_name=self.qdrant.collection_name,
                scroll_filter=models.Filter(must=[
                    models.FieldCondition(key="content_hash", match=models.MatchValue(value=content_hash)),
                    models.FieldCondition(key="kg_status", match=models.MatchValue(value="completed"))
                ]), limit=1
            )
            return len(res[0]) > 0
        except: return False

    def _flush_kg_batch(self, buffer: List[Dict], domain: str = "general"):
        """
        批量抽取并入库，成功后更新 Qdrant 状态
        集成视觉逻辑化抽取
        """
        stats = {"visual_extracted": 0, "entities_linked": 0, "new_entities": 0}
        extractor = KGRegistry.get_agent("extractor")
        inspector = KGRegistry.get_agent("inspector")
        resolver = KGRegistry.get_agent("resolution")
        if not extractor: return

        # 懒加载 VLMService，只有在需要时才占用显存
        from skills.vlm_service import VLMService

        logger.info(f"📦 [KG-Batch] 开始处理 {len(buffer)} 个切片...")

        # --- 步骤 A: 视觉增强（针对含有图片的切片） ---
        processed_items = []
        for item in buffer:
            text_content = item["text"]
            # 检查 metadata 中是否存有临时图片路径 (由 doc_parser 生成)
            image_path = item.get("metadata", {}).get("image_path")

            if image_path and os.path.exists(image_path):
                try:
                    logger.info(f"👁️  [VLM] 探测到架构图/插图，启动 A4000 视觉识别...")
                    vlm = VLMService.get_instance()
                    # 调取我们在 2.1 跑通的描述方法
                    image_desc = vlm.describe_image(image_path)

                    # 🔥 核心：将视觉逻辑融入文本
                    text_content += f"\n\n【图片视觉逻辑描述】: {image_desc}"
                    logger.info(f"✅ [VLM] 识别完成，描述字数: {len(image_desc)}")
                except Exception as ve:
                    logger.error(f"⚠️ [VLM] 视觉解析跳过: {ve}")

            item["text"] = text_content
            processed_items.append(item)

        # --- 步骤 B: 执行原有的图谱抽取流程 ---
        try:
            processed_buffer = []
            for item in buffer:
                enriched_text = item["text"]

                # 如果该切片带有图片字节
                if item.get("metadata", {}).get("image_bytes"):
                    logger.info(f"👁️  [VLM] 探测到图片，启动 A4000 视觉识别: {item['id'][:8]}...")
                    from skills.vlm_service import VLMService
                    vlm = VLMService.get_instance()

                    # 调用 A4000 运行 Qwen2-VL
                    image_desc = vlm.describe_image(item["metadata"]["image_bytes"])

                    # 核心操作：将视觉描述拼接进文本，喂给后续的 ExtractorAgent
                    enriched_text = f"{enriched_text}\n【视觉补充描述】: {image_desc}"

                item["text"] = enriched_text
                processed_buffer.append(item)
            # 1. 执行批量 LLM 抽取
            batch_data = extractor.run_batch(processed_buffer, domain=domain)
            results = batch_data.get("results", [])
            successful_ids = []

            for i, res in enumerate(results):
                # 🔥 2.3 增强：如果当前切片是表格，强行注入一个“表格实体”
                # 这样 Resolver 就能把文字引用的 Table_1 和这个实体对齐
                if processed_items[i].get("metadata", {}).get("is_table"):
                    table_label = "表格" # 逻辑上可以从 content 提取更细的标识
                    res["entities"].append({
                        "name": table_label,
                        "type": "Table_Object",
                        "desc": "文档中的结构化数据表"
                    })

            successful_chunk_ids = []

            for i, res in enumerate(results):
                if i >= len(buffer): break
                # 1. 检索全局存量
                global_refs = []
                if self.nebula and hasattr(self.nebula, 'es_store') and self.nebula.es_store:
                    for ent in res.get('entities', []):
                        vids = self.nebula.es_store.search_entities(ent['name'], top_k=1)
                        for v in vids:
                            old = self.nebula.get_entity_detail(v)
                            if old: global_refs.append(old)

                # 2. 质量审计与消解
                refined_kb = inspector.run(buffer[i]["text"], res)
                # 🔥 传入全局参考
                res_out = resolver.run(refined_kb.get('entities', []), refined_kb.get('relations', []), global_ref=global_refs)

                # 3. 统计
                m = res_out.get("metrics", {})
                metrics["total_entities"] += m.get("total_extracted", 0)
                metrics["entities_linked"] += m.get("linked_count", 0)
                if buffer[i].get("is_visual"):
                    metrics["visual_entities"] += m.get("total_extracted", 0)

                self.nebula.upsert_graph(res_out, buffer[i]["id"])
                successful_ids.append(buffer[i]["id"])

            if successful_ids: self._mark_kg_success_in_qdrant(successful_ids)
        except Exception as e:
            logger.error(f"Batch Failed: {e}")
        return metrics

    def _mark_kg_success_in_qdrant(self, chunk_ids: List[str]):
        """
        强制更新 Qdrant 状态位为 completed
        """
        try:
            # 批量更新提高效率
            for cid in chunk_ids:
                self.qdrant.client.set_payload(self.qdrant.collection_name,
                                               {"kg_status": "completed"},
                                               [cid],
                                               wait=False)
            logger.info(f"✅ 已更新 {len(chunk_ids)} 个切片的图谱状态为 completed")
        except Exception as e:
            logger.error(f"❌ 更新状态位失败: {e}")
