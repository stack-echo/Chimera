# 🦄 Chimera (v0.5.0)

> **The Observable AI Agent Platform.**  
> **面向企业的可观测多智能体 PaaS 平台。**

Chimera 是一个基于 **Go (Control Plane)** + **Python (Inference Runtime)** 双核架构的企业级 AI 基础设施。它不仅仅是一个 RAG 系统，更是一个通用的智能体运行时环境。它解耦了“业务应用”与“底层知识”，并提供了从网关到 LLM 推理的**全链路可观测性 (Observability)**。

## ✨ v0.5.0 核心特性：平台化元年

### 🔬 全链路可观测 (Observability Loop)
- **白盒化推理**：不再是黑盒问答。系统实时追踪智能体的“思考过程 (Thought Chain)”。
- **精准计量**：Python 运行时精确统计 Token 消耗与推理耗时，并通过 gRPC 回传给 Go 控制面进行持久化审计。
- **分布式追踪**：集成 **OpenTelemetry (SigNoz)**，提供跨语言（Go -> Python）的函数级性能分析。

### 🏗️ 双核分离架构 (Dual-Core Architecture)
- **控制面 (Go)**：负责多租户鉴权、业务逻辑路由、日志归档与数据源管理。
- **计算面 (Python)**：基于 **LangGraph** 的动态工作流引擎，无状态设计，支持高并发扩展。
- **通用协议**：通过 `runtime.proto` 定义了标准化的 `RunAgent` 和 `SyncDataSource` 接口，支持任意 Agent 接入。

### 🔌 热插拔资源 (Hot-Pluggable Resources)
- **ETL 流水线**：标准化的 `Connector` 接口。v0.5.0 内置 **Docling** 文件解析器，支持 PDF/Markdown 的视觉理解与语义切分。
- **多租户隔离**：通过 `OrgID` 和 `KB_ID` 实现向量数据库 (Qdrant) 的逻辑隔离。
- **数据源抽象**：从单一的“文件”升级为“数据源 (DataSource)”，为接入飞书、钉钉、网页爬虫做好准备。

## 🛠️ 技术栈

### 控制面 (Backend-Go)
- **框架**: Gin, gRPC
- **存储**: PostgreSQL (元数据/审计日志), Redis (缓存/会话)
- **中间件**: JWT 鉴权, OpenTelemetry SDK

### 运行时 (Agent-Runtime)
- **核心**: Python 3.11, LangGraph, gRPC Server
- **AI 能力**: Docling (文档解析), OpenAI SDK / DeepSeek (推理), Sentence-Transformers (向量化)
- **知识存储**: Qdrant (向量), NebulaGraph (图谱 - 预览中), MinIO (对象存储)

## 🚀 快速开始

### 1. 启动基础设施
```bash
cd deploy
docker-compose up -d
# 启动: PostgreSQL, Redis, MinIO, Qdrant, SigNoz
```

### 2. 启动 Python 运行时
```bash
cd chimera-agent-runtime
# 1. 安装依赖 (推荐使用 venv)
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 务必填入 DEEPSEEK_API_KEY 和数据库配置

# 3. 启动服务
python main.py
# 🚀 Runtime running on :50051
```

### 3. 启动 Go 控制面
```bash
cd backend-go
# 1. 安装依赖
go mod download

# 2. 启动服务 (自动执行数据库迁移)
go run cmd/server/main.go
# 🚀 Server running on :8080
```

### 4. 启动前端
```bash
cd frontend-vue
npm install && npm run dev
# 访问: http://localhost:5173
```

## 📈 版本演进

| 版本 | 核心里程碑 | 状态 |
| :--- | :--- | :--- |
| **v0.1.0** | 基础 RAG 链路，支持 PDF 上传与问答 | ✅ |
| **v0.2.0** | 用户认证系统 (JWT) 与代码重构 | ✅ |
| **v0.3.0** | 文档视觉理解 (Docling) + 可验证问答 | ✅ |
| **v0.4.0** | 多租户与隔离架构 | ✅ |
| **v0.5.0** | **平台化重构 (Current)** <br> - 引入 `Application` 与 `DataSource` 概念 <br> - 实现 Go/Python 业务数据闭环 <br> - 落地 Qdrant 多租户检索 | 🎉 |
| **v0.6.0** | **可视与连接 (Coming Soon)** <br> - 监控中台 Dashboard (Token/耗时统计) <br> - 飞书/钉钉连接器 <br> - GraphRAG 实装 | 🚧 |

## 🤝 贡献
欢迎提交 Issue 和 PR！让我们一起构建下一代 AI 基础设施。
```
