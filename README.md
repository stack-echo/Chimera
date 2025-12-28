# 🦄 Chimera-RAG (v0.3.5)

Chimera-RAG 是一个基于 **Go + Python** 混合架构的企业级 EHS 安全合规知识库助手。它实现了完整的 RAG (检索增强生成) 链路，具备**文档视觉理解**与**可验证的智能问答**能力。

## ✨ 核心特性

### 🧠 AI 内核：真正"看见"文档
- **Docling 集成**：替换 PyMuPDF，系统现在能**视觉化理解**文档布局、表格和层级结构。
- **语义分块**：基于标题和段落的智能切片 (`HybridChunker`)，保持上下文完整性。
- **视觉解析**：准确识别文档中的表格、列表、标题等结构化元素。

### 👁️ 用户界面：可信的答案
- **引用与验证**：AI 回答包含可点击的引用标记 (如 `[Page 4]`)。
- **即时 PDF 预览**：
  - 分屏视图：左侧聊天，右侧文档。
  - **点击跳转**：点击引用自动滚动 PDF 到对应页面。
- **流式交互**：完整的 SSE (Server-Sent Events) 支持，实时显示"思考"过程。

### 🏗️ 架构升级
- **MinIO 流式代理**：安全的文件流传输，不暴露公有 URL。
- **清晰架构**：Python 服务重构为 `core`, `tools`, `service` 三层，提升可扩展性。
- **可验证性设计**：每个回答都可追溯到原始文档的具体位置。

## 🛠️ 技术栈

### 后端架构
- **网关层**: Golang, Gin, gRPC, Redis 队列
- **存储层**: MinIO (文档), Qdrant (向量), PostgreSQL (元数据)
- **AI 服务**: Python 3.11, Docling, Sentence-Transformers, OpenAI SDK
- **通信协议**: HTTP/2, gRPC, Server-Sent Events

### 前端技术
- **框架**: Vue 3 + TypeScript + Vite
- **UI 组件**: Arco Design
- **文档预览**: PDF.js 集成
- **实时通信**: SSE + WebSocket 备用

## 🚀 快速开始

### 1. 启动基础设施
```bash
cd deploy
docker-compose up -d
# 启动: PostgreSQL, Redis, MinIO, Qdrant
```

### 2. 启动 AI 服务 (Python)
```bash
cd ai-service-python
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入必要的 API 密钥

# 3. 启动服务
python main.py
# 服务运行在: http://localhost:50051 (gRPC)
```

### 3. 启动后端网关 (Go)
```bash
cd backend-go
# 1. 安装依赖
go mod download

# 2. 配置环境变量
export JWT_SECRET=your_secret_key
export DATABASE_URL=postgres://user:pass@localhost:5432/rag_db

# 3. 启动服务
go run cmd/server/main.go
# 服务运行在: http://localhost:8080 (HTTP)
```

### 4. 启动前端
```bash
cd frontend-vue
# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
# 访问: http://localhost:5173
```
📈 版本演进

已发布版本

v0.1.0: 基础 RAG 链路，支持 PDF 上传与问答

v0.2.0: 完整的用户认证系统 (JWT + PostgreSQL)，重构的python代码

v0.3.0: 🎉 本版本 - 文档视觉理解 + 可验证问答