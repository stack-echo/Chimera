# runtime/skills/reranker.py

from typing import List, Dict, Any
import numpy as np

class CognitiveReranker:
    @staticmethod
    def _is_dominated(candidate: Dict, others: List[Dict]) -> bool:
        """
        判断 candidate 是否被 others 中的某个节点“支配”
        支配定义：如果 B 在所有维度都不如 A，且至少在一个维度比 A 差，则 A 支配 B。
        """
        c_v = candidate['metrics']['vector']
        c_g = candidate['metrics']['graph']
        c_h = candidate['metrics']['hierarchy']

        for o in others:
            o_v = o['metrics']['vector']
            o_g = o['metrics']['graph']
            o_h = o['metrics']['hierarchy']

            # 如果存在一个 o，在所有维度都优于或等于 c
            if o_v >= c_v and o_g >= c_g and o_h >= c_h:
                # 且至少有一个维度严格大于 c
                if o_v > c_v or o_g > c_g or o_h > c_h:
                    return True
        return False

    @staticmethod
    def skyline_filter(
            vector_results: List[Dict],
            graph_scores: Dict[str, float],
            top_k: int = 5
    ) -> List[Dict]:
        """
        落地 BookRAG 多维 Skyline 过滤算法
        """
        if not vector_results:
            return []

        # 1. 准备评价指标 (Normalization)
        candidates = []
        max_v = max([hit.get('score', 0.1) for hit in vector_results]) or 1.0
        max_g = max(graph_scores.values()) if graph_scores else 1.0

        for hit in vector_results:
            cid = str(hit.get('metadata', {}).get('chunk_id') or hit.get('id'))

            # 维度 A: 语义分 (0-1)
            v_score = hit.get('score', 0.0) / max_v

            # 维度 B: 拓扑分 (0-1)
            g_score = graph_scores.get(cid, 0.0) / max_g

            # 维度 C: 层级分 (深度越深，得分越高，越具像)
            # Level 3 (Segment) > Level 1 (Chapter)
            level = hit.get('metadata', {}).get('level', 0)
            h_score = min(level / 5.0, 1.0)

            candidates.append({
                "raw": hit,
                "metrics": {
                    "vector": v_score,
                    "graph": g_score,
                    "hierarchy": h_score
                }
            })

        # 2. 计算 Skyline 集合 (非支配解)
        skyline = []
        for i, c in enumerate(candidates):
            # 检查是否有其他节点在三个维度上都比 c 强
            if not CognitiveReranker._is_dominated(c, candidates):
                skyline.append(c)

        # 3. 结果精选
        # 如果 Skyline 里的解太多，按综合加权分排个序
        for s in skyline:
            m = s['metrics']
            # 这里的权重平衡了：细节(0.4) + 结构(0.4) + 层级深度(0.2)
            s['combined'] = m['vector'] * 0.4 + m['graph'] * 0.4 + m['hierarchy'] * 0.2

        skyline.sort(key=lambda x: x['combined'], reverse=True)

        # 返回原始数据格式
        final_results = [s['raw'] for s in skyline[:top_k]]

        # 兜底逻辑：如果 Skyline 过滤得太狠，解太少，用 Top-K 补齐
        if len(final_results) < top_k:
            existing_ids = {str(r.get('id')) for r in final_results}
            vector_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            for v in vector_results:
                if len(final_results) >= top_k: break
                if str(v.get('id')) not in existing_ids:
                    final_results.append(v)

        return final_results