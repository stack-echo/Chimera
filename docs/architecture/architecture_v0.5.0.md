好的，基于我们刚才的讨论，我已经对 **Chimera-RAG v0.5.0 架构白皮书** 进行了全面更新。

主要变更点：
1.  **领域模型**：正式纳入 **User** 和 **OrganizationMember**，明确了多租户下的用户归属关系。
2.  **通信协议**：更新 `runtime.proto` 定义，增加了 **`RunSummary`** 消息以支持业务监控数据回传。
3.  **开发路线图**：明确了监控中台的 **“v0.5.0 存数据，v0.6.0 做展示”** 的分期策略。

---

# 🦄 Chimera-RAG v0.5.0 技术架构白皮书

> **版本**: v0.5.0 (Platform Era)  
> **核心定位**: 面向企业的可观测多智能体 PaaS 平台  
> **最后更新**: 2025-12-30

---

## 1. 核心愿景 (Vision)

Chimera 从单一 RAG 工具转型为 **AI 基础设施平台**。
核心差异化卖点：
1.  **全链路可观测性 (Observability)**：不仅仅监控服务器状态，更要监控智能体的“思考路径”、Token 消耗与推理耗时。
2.  **资源解耦 (Decoupling)**：实现“应用”与“知识”的分离。知识库作为底层资产，可被多个应用复用。
3.  **多模态 ETL**: 支持 PDF、飞书、网页等多种数据源的统一接入。

---

## 2. 系统架构概览 (System Architecture)

系统采用 **双核分离架构**，Go 负责业务控制与数据持久化，Python 负责 AI 核心计算。

```mermaid
graph TD
    User[用户/前端] -->|HTTP/SSE| Gateway[Go 控制面]
    
    subgraph "Control Plane (Go)"
        Gateway --> Auth[鉴权模块]
        Gateway --> Biz[业务逻辑]
        Gateway --> LogMgr[监控日志入库]
    end
    
    subgraph "Inference Plane (Python)"
        Gateway -->|gRPC (Runtime)| Runtime[Python 运行时]
        Runtime -->|LangGraph| Workflow[智能体工作流]
        Runtime -->|Connectors| ETL[数据源同步]
    end
    
    subgraph "Storage Layer"
        PG[(PostgreSQL)] -->|用户/应用/日志| Gateway
        MinIO[(MinIO)] -->|文件存储| Runtime
        Qdrant[(Qdrant)] -->|向量索引| Runtime
        Nebula[(NebulaGraph)] -->|知识图谱| Runtime
    end
    
    subgraph "Observability"
        Runtime -.->|OTel Trace| SigNoz[SigNoz (运维层)]
        Gateway -.->|Biz Logs| PG[Postgres (业务层)]
    end
```

---

## 3. 核心领域模型 (Domain Models)

为了支撑多租户与权限管理，我们定义了以下实体关系。

| 概念 | 说明 | 对应关系 |
| :--- | :--- | :--- |
| **User (用户)** | 系统的登录主体与操作执行者。 | N:N Organization (通过 Member表) |
| **Organization (组织)** | 租户边界。资源（应用、知识库）的所有权单位。 | 1:N User |
| **OrganizationMember (成员)** | **核心关联表**。定义 User 在 Organization 中的角色 (Owner/Admin/Member)。 | - |
| **Application (应用)** | 业务入口。例如"HR助手"。包含 Prompt、关联的 KB ID。 | N:N KnowledgeBase |
| **KnowledgeBase (知识库)** | 逻辑容器。仅作为标签存在，不直接存数据。 | 1:N DataSource |
| **DataSource (数据源)** | 真正的数据实体。可以是文件、飞书链接。 | 1:N Vectors |

---

## 4. 关键协议与数据流 (Protocols & Data Flow)

### 4.1 通信协议 (`api/proto/runtime.proto`)

为支持监控数据回传，协议进行了重要升级：

*   **`RunAgent`**: 通用执行接口。
*   **`RunAgentResponse`**:
    *   `type="thought"`: 思考过程 (Thought Chain)。
    *   `type="delta"`: 答案片段 (Token Stream)。
    *   `type="summary"`: **(新增)** 执行摘要，包含 Token 统计、总耗时、最终状态。

```protobuf
message RunAgentResponse {
  string type = 1;      // "thought", "delta", "summary"
  string payload = 2;   // 内容
  AgentMeta meta = 3;   // OTel TraceID
  RunSummary summary = 4; // 仅在 type="summary" 时存在
}

message RunSummary {
  int32 total_tokens = 1;
  int32 prompt_tokens = 2;
  int32 completion_tokens = 3;
  int64 total_duration_ms = 4;
}
```

### 4.2 智能体运行闭环 (The Loop)

1.  **Go**: 校验用户权限 (`OrganizationMember`)。
2.  **Go**: 构造 `RunAgentRequest`，注入 `app_config` (含 KB IDs)。
3.  **Python**: 执行 LangGraph 工作流。
4.  **Python**:
    *   流式返回 `thought` 和 `delta`。
    *   **结束时**: 统计 Token 用量，发送 `type="summary"` 消息。
5.  **Go**:
    *   转发 `thought`/`delta` 给前端。
    *   **拦截 `summary`**: 将 TraceID、Token、耗时、用户ID 写入 Postgres 的 `app_run_logs` 表。

---

## 5. 监控中台分期策略 (Observability Strategy)

监控中台涉及全栈开发，为降低 v0.5.0 风险，采取 **“后端先行，前端跟进”** 的策略。

### ✅ Phase 1: 数据蓄水期 (v0.5.0)
**目标**：确保业务监控数据被完整生产并持久化。
*   **Python**: 实现 Token 计数器，在 gRPC 结束帧回传统计数据。
*   **Go**: 建立 `app_run_logs` 表，完成日志清洗与入库。
*   **SigNoz**: 确保 TraceID 能够串联 Go 和 Python 的链路。
*   *此时暂无前端图表，数据沉淀在数据库中。*

### 📅 Phase 2: 数据可视化期 (v0.6.0)
**目标**：基于沉淀的数据构建 `/admin/insights` 面板。
*   **Dashboard**: Token 消耗趋势图、平均响应时间、活跃应用排行。
*   **Trace View**: 点击某次对话，展示详细的“瀑布流”与 Prompt 详情。

---

## 6. 开发规范 (Guidelines)

### 6.1 Go (Control Plane)
*   **鉴权优先**: 任何业务操作前，必须先查询 `OrganizationMember` 确认用户权限。
*   **日志入库**: 在 `StreamChat` 循环结束时，必须确保 `AppRunLog` 写入成功，这是计费和审计的基础。

### 6.2 Python (Runtime)
*   **Token 统计**: 在 `LLMClient` 中必须准确获取 `usage` 信息。
*   **无状态**: 不要依赖 Python 内存存用户状态，所有上下文依赖 Redis 或 gRPC 入参。

### 6.3 前端 (Frontend)
*   **SSE 解析**: 预留 JSON 解析能力。
    *   当前: `THOUGHT: ...` (字符串前缀)
    *   未来: `data: {"type": "thought", ...}` (JSON 对象)
*   **状态反馈**: 知识库导入是异步的，需轮询 `DataSource` 状态 (`pending` -> `active`/`error`)。

---

## 7. 版本交付清单 (Release Checklist)

### v0.5.0 (Current)
*   [x] 核心重构：`RuntimeService` 取代 `RagService`。
*   [x] 存储层：Qdrant 向量存储实现。
*   [ ] **协议升级**：添加 `RunSummary` 到 Proto 并重新生成。
*   [ ] **数据埋点**：Python 端实现 Token 统计与回传。
*   [ ] **日志落盘**：Go 端实现 `AppRunLog` 表与写入逻辑。

### v0.6.0 (Next)
*   [ ] 监控中台前端 UI (`/admin/insights`)。
*   [ ] 飞书/钉钉连接器集成。
*   [ ] NebulaGraph 图谱构建流水线。

---

*本白皮书位于项目根目录 `docs/architecture_v0.5.0.md`，作为团队协作的基准文档。*