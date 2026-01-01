# 🌌 Chimera v0.6.0 架构设计方案：Graph-Native RAG

## 1. 核心设计哲学 (Design Philosophy)

我们需要摒弃“图谱只是外挂”的想法，转向 **“结构-语义双螺旋”** 架构。
参考 **Cog-RAG** 和 **BookRAG**，我们将数据分为两层：
1.  **语义层 (Semantic Layer)**: 也就是 Qdrant 里的 Vector Chunks。负责“模糊匹配”和“广度召回”。
2.  **认知层 (Cognitive Layer)**: 也就是 NebulaGraph 里的 Entities & Relations。负责“精确导航”和“多跳推理”。

**v0.6.0 的差异化卖点：**
*   **可解释性**: 用户不仅能看到引用的文档片段，还能看到一张**思维导图（子图）**，显示 AI 是如何从“A实体”关联到“B实体”的。
*   **动态性**: 不做静态图，而是通过 LLM 在 ETL 阶段动态提取（ProPEX 思想）。

---

## 2. 数据模型设计 (Schema)

在 **NebulaGraph** 中，我们需要定义一套通用的 Schema，既要简单又要能承载复杂业务。

### 图空间: `chimera_kb`

#### Tags (顶点类型)
1.  **`Entity`** (实体)
    *   `name` (string): 实体名 (Primary Key, e.g., "DeepSeek")
    *   `type` (string): 类型 (e.g., "Model", "Organization")
    *   `desc` (string): 摘要描述 (用于 disambiguation)
2.  **`Chunk`** (文档切片 - **关键！将图与向量联系起来**)
    *   `chunk_id` (string): 对应 Qdrant 里的 Point ID
    *   `source_id` (int): 对应 MySQL 的 DataSource ID

#### Edge Types (边类型)
1.  **`RELATION`** (实体间关系)
    *   `desc` (string): 关系描述 (e.g., "developed_by", "competes_with")
    *   `weight` (double): 权重
2.  **`MENTIONED_IN`** (实体出现在文档中)
    *   **这是连接 Cog-RAG “双超图”概念的关键**。
    *   方向: `Entity` -> `Chunk`。表示“这个实体在这个切片里被提到了”。

---

## 3. 阶段一：图谱构建流水线 (Graph ETL)

参考 **ProPEX-RAG** 和 **TAdaRAG (Stage 1)**，我们不使用传统的 BERT 模型做 NER，而是利用 **LLM (DeepSeek) + Prompt** 进行高质量抽取。

这部分逻辑将在 `runtime` 中实现一个新的 LangGraph 工作流：`KGBuildWorkflow`。

### 流程步骤：
1.  **Chunking (现有)**: Docling 解析 PDF 得到文本块。
2.  **Extraction (新增)**:
    *   对每个 Chunk，并发调用 LLM（使用 `ProPEX` 风格的 Prompt）。
    *   **Prompt**: "从以下文本中提取实体和关系，输出 JSON 格式 `[{head, relation, tail}, ...]`。注意：忽略通用词汇。"
3.  **Resolution (新增 - 实体对齐)**:
    *   **局部对齐**: 在内存中合并同名实体。
    *   **同义词合并**: (v0.6.1考虑) 使用 Embedding 相似度判断 "LLM" 和 "Large Language Model" 是否为一个点。
4.  **Ingestion (新增)**:
    *   写入 NebulaGraph：
        *   `INSERT VERTEX Entity ...`
        *   `INSERT EDGE RELATION ...`
        *   **关键**: `INSERT EDGE MENTIONED_IN (Entity_ID -> Chunk_ID)`

---

## 4. 阶段二：双路检索与推理 (Inference)

参考 **HyperbolicRAG** 和 **Microsoft Azure RAG** 的最佳实践，我们采用 **“混合检索 + 动态重排”** 策略。

### 运行时工作流 (`workflows/graph_chat.py`):

#### Step 1: 意图分析与关键词提取 (Query Parsing)
*   LLM 分析用户 Query，提取出 **Core Entities** (核心实体)。
*   *例子*: 用户问 "DeepSeek 和 OpenAI 的区别？" -> 提取 `["DeepSeek", "OpenAI"]`。

#### Step 2: 双路并发召回 (Parallel Retrieval)

*   **路 A: 向量检索 (Vector Search)**
    *   用 Query Embedding 去 Qdrant 搜 Top-K Chunks。
    *   *目的*: 兜底，防止图谱里没有覆盖到的细节。

*   **路 B: 图谱遍历 (Graph Traversal - Subgraph Retrieval)**
    *   **Anchor**: 在 NebulaGraph 中找到 `["DeepSeek", "OpenAI"]` 这两个节点。
    *   **Expansion (扩散)**: 向外跳 1~2 步 (1-2 hop)，获取邻居节点和关系。
    *   **Pruning (剪枝)**: 使用 LLM 或 相似度 过滤掉不相关的邻居（比如过滤掉权重低的边）。
    *   **Linking**: 通过 `MENTIONED_IN` 边，找到这些实体关联的 `Chunk`。

#### Step 3: 上下文融合 (Context Fusion)
*   将 **路 A 的文本** 和 **路 B 的三元组/关系描述** 拼接在一起。
*   **Prompt 增强**:
    ```text
    【知识图谱路径】:
    DeepSeek --(developed_by)--> High-Flyer
    DeepSeek --(competes_with)--> OpenAI
    
    【相关文档片段】:
    ...
    ```

#### Step 4: 答案生成与可视化数据输出
*   LLM 生成答案。
*   **观测性 (核心卖点)**: 将 Step 2 中检索到的 **子图 (Nodes + Edges)** 序列化为 JSON，传回给前端。前端用 D3.js 或 ECharts Graph 渲染出来！

---

## 5. 开发计划 (Action Plan)

### 基础设施与 ETL (The Skeleton)
1.  **Nebula Store**: 完善 `core/stores/nebula_store.py`，实现 `upsert_vertices`, `upsert_edges`。
2.  **Graph ETL Workflow**: 开发 `workflows/kg_builder.py`，实现 LLM 抽取逻辑。
3.  **Hook**: 修改 `runtime_service.py` 的 `SyncDataSource`，在写入 Qdrant 的同时，触发 Graph ETL。

### 检索逻辑 (The Brain)
1.  **Graph Search Skill**: 在 `core/stores/nebula_store.py` 中实现 `get_subgraph(entity_names, hops=2)`。
2.  **Hybrid Workflow**: 创建新的 `GraphChatWorkflow`，整合 Vector + Graph 检索结果。
3.  **Prompt Engineering**: 调优实体抽取的 Prompt（参考 ProPEX），保证抽取出来的图谱质量不至于太脏。

### 前端可视化 (The Face)
1.  **API 升级**: 确保 `RunAgentResponse` 的 `meta` 或 `payload` 能携带 `subgraph_json` 数据。
2.  **Vue 组件**: 在 `Insights.vue` 或聊天窗口侧边栏，增加一个 **"知识网络"** 面板，渲染本次回答用到的知识图谱。

---

## 6. 代码预览：ProPEX 风格的抽取 Prompt

这是我们将要用在 Python 端的核心 Prompt 模板：

```yaml
# chimera-agents-runtime/prompts/extract_triplets.yaml
system: |
  你是一个专业的知识图谱构建专家。你的任务是从给定的文本片段中提取结构化的知识三元组。
  
  【提取规则】：
  1. 实体 (Nodes): 识别人名、组织、技术术语、地点、时间等关键概念。
  2. 关系 (Edges): 识别实体之间明确的动作或属性关联。
  3. 原子性: 实体和关系应尽可能简洁（如"苹果公司"而不是"著名的苹果公司"）。
  4. 格式: 输出 JSON 列表: [{"head": "实体A", "relation": "关系", "tail": "实体B"}, ...]

  【待处理文本】:
  {{ text_chunk }}

  【输出】:
```

---
