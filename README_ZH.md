# 🦄 Chimera (v0.6.0)

> **The Observable AI Agent Platform.**
> **面向企业的可观测多智能体 PaaS 平台。**

[![English](https://img.shields.io/badge/-English-0077b5?style=for-the-badge)](README_ZH.md)
[![中文](https://img.shields.io/badge/-中文-d52a1d?style=for-the-badge)](README_ZH.md)


Chimera 是一个基于 **Go (Control Plane)** + **Python (Inference Runtime)** 双核架构的企业级 AI 基础设施。

在 **v0.6.0** 中，我们完成了**Open Core（核心开源）** 架构重构，实现了核心能力与企业级特性的解耦。现在，Chimera 既是一个开箱即用的轻量级 RAG 系统，也是一个支持复杂业务扩展的 AI PaaS 平台。

## ✨ v0.6.0 新特性：架构破局

### 🧬 Open Core 插件化架构
- **核心解耦**：彻底剥离了业务逻辑与 AI 核心。Python 运行时引入 **工厂模式 (Factory)** 与 **动态加载器 (Loader)**，实现“一套代码，两种形态”。
- **物理隔离**：企业级代码（如飞书集成、图谱构建）移入 `enterprise/` 目录，开源仓库保持纯净。
- **Go 服务分层**：引入 `DataSourceService` 与 `ChatService`，配合 `Registry` 机制，实现无侵入式的功能注入。

### 🔬 全链路可观测 (Observability)
- **白盒化推理**：实时追踪智能体的“思考过程 (Thought Chain)”。
- **精准计量**：Python 运行时精确统计 Token 消耗与推理耗时，通过 gRPC 回传进行持久化审计。
- **分布式追踪**：集成 **OpenTelemetry (SigNoz)**，提供跨语言（Go -> Python）的函数级性能分析。

### 🧠 混合增强检索 (Hybrid RAG)
- **向量检索 (OSS)**：基于 **Qdrant** 的高性能向量搜索。
- **图谱增强 (Enterprise)**：基于 **NebulaGraph** 的知识图谱构建与检索 (GraphRAG)，解决复杂推理问题。

---

## 🛠️ 功能矩阵

| 功能模块 | 🟢 开源社区版 (Community) | 🔵 企业商用版 (Enterprise) |
| :--- | :--- | :--- |
| **检索模型** | 向量检索 (Qdrant) | **GraphRAG (向量 + 图谱)** |
| **数据源** | 本地文件 (PDF/Markdown) | **飞书 / 钉钉 / Web Crawler** |
| **文档解析** | Docling (OCR/Layout) | Docling + **知识抽取 (NER/RE)** |
| **部署架构** | 单机 Docker Compose | **高可用集群 / K8s** |
| **构建体系** | 标准镜像 | **分层构建 (Core + Plugins)** |

---

## 🏗️ 目录结构

```text
Chimera/
├── deploy/               # Docker 编排文件 (OSS & EE)
├── server/               # [Go] 控制面
│   ├── cmd/
│   │   ├── server/       # 🟢 开源版入口
│   │   └── server-ee/    # 🔵 企业版入口 (注入 Plugin)
│   ├── internal/core/    #    接口定义与注册表
│   └── enterprise/       # 🔒 闭源业务逻辑
├── runtime/              # [Python] 计算面
│   ├── core/
│   │   ├── managers/     #    业务逻辑 (ETL, Inference)
│   │   └── connectors/   #    基础连接器 (File)
│   ├── enterprise/       # 🔒 闭源插件 (Feishu, Nebula, KG)
│   └── loader.py         #    动态加载器
└── web/                  # [Vue3] 前端
```

---

## 🚀 快速开始

### 1. 启动开源版 (Community Edition)

适合个人开发者或小团队，轻量级，无需图数据库。

```bash
cd deploy
# 启动 Postgres, Redis, MinIO, Qdrant, SigNoz, Server, Runtime
docker-compose up -d
```

### 2. 启动企业版 (Enterprise Edition)

适合需要飞书集成或图谱增强的企业环境。（需拥有 `enterprise` 源码目录）

```bash
cd deploy
# 启动全量服务 (包含 NebulaGraph 集群)
# 注意：会自动使用 Dockerfile.ee 构建包含 enterprise 代码的镜像
docker-compose -f docker-compose-ee.yml up -d --build
```

---

## 💻 本地开发指南

如果你需要修改代码，请按照以下方式启动。

### Python Runtime

```bash
cd runtime
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
# loader.py 会自动检测当前目录下是否有 'enterprise' 文件夹
# 如果没有，自动降级为 Core 模式
python main.py
```
> **提示**: 如果看到日志 `ℹ️ No enterprise directory found`，说明运行在开源模式。

### Go Server

```bash
cd server
# 1. 安装依赖
go mod download

# 2. 启动开源版 (纯净模式)
go run cmd/server/main.go

# 3. 启动企业版 (注入模式)
# 前提：server/enterprise 目录存在
go run cmd/server-ee/main.go
```
> **提示**: 企业版启动时会打印 `🔓 [Enterprise] Loading Feishu Plugin...`。

---

## 📈 版本演进

| 版本 | 里程碑                                                                          | 状态 |
| :--- |:-----------------------------------------------------------------------------| :--- |
| **v0.4.0** | 多租户与隔离架构                                                                     | ✅ |
| **v0.5.0** | 引入图谱双路召回与 SigNoz 监控                                                          | ✅ |
| **v0.6.0** | **商业化架构重构 (Current)** <br> - Open Core 双核分离 <br> - 插件化连接器与存储 <br> - 物理隔离构建体系 | 🎉 |
| **v0.7.0** | **记忆与权限 (Planning)** <br> - Redis Session 长期记忆 <br> - RBAC 权限体系              | 🚧 |

## 📄 开源协议 (License)

本项目采用 **GNU Affero General Public License v3.0 (AGPL v3)** 协议开源。

*   **允许**: 免费使用、修改、学习。
*   **必须**: 如果您基于本项目通过网络提供服务（SaaS），必须开源您的修改代码。
*   **商业授权**: 如需闭源商业使用或获取企业版源码，请联系作者获取授权。

---

## 🤝 贡献

欢迎提交 Issue 和 PR！对于新的数据源连接器，请遵循 `core/connectors/base.py` 中的接口规范。

*   **核心功能**: 请提交至 `server/internal` 或 `runtime/core`。
*   **新插件**: 建议先提交 Issue 讨论。