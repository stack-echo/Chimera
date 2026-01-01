# 🦄 Chimera (v0.6.0)

> **The Observable AI Agent Platform.**
> **An Enterprise-grade PaaS for Multi-Agent Orchestration & RAG.**

[![License](https://img.shields.io/badge/license-AGPL%20v3-blue.svg)](LICENSE)
[![Go Report Card](https://goreportcard.com/badge/github.com/yourname/chimera)](https://goreportcard.com/report/github.com/yourname/chimera)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

[![English](https://img.shields.io/badge/-English-0077b5?style=for-the-badge)](README_ZH.md)
[![中文](https://img.shields.io/badge/-中文-d52a1d?style=for-the-badge)](README_ZH.md)

**Chimera** is a dual-core AI infrastructure built on **Go (Control Plane)** and **Python (Inference Runtime)**. It decouples business logic from AI capabilities, providing full-stack observability from the API gateway down to LLM inference.

In **v0.6.0**, we have transitioned to an **Open Core Architecture**. This major refactoring decouples the core capabilities from enterprise-specific features, making Chimera both an out-of-the-box lightweight RAG system and a scalable PaaS platform for complex enterprise scenarios.

---

## ✨ v0.6.0 Highlights: The Architecture Shift

### 🧬 Open Core & Plugin Architecture
- **Decoupling**: Business logic and AI core are strictly separated. The Python Runtime introduces **Factory Patterns** and **Dynamic Loaders** to support "One Codebase, Two Modes".
- **Physical Isolation**: Enterprise-grade assets (e.g., Feishu/Lark integration, Knowledge Graph construction) are moved to the `enterprise/` directory, keeping the open-source repository clean.
- **Service Layering**: The Go server introduces `DataSourceService` and `ChatService`, combined with a `Registry` mechanism for non-intrusive feature injection.

### 🔬 Full-Stack Observability
- **White-Box Inference**: Trace the agent's "Thought Chain" in real-time.
- **Precise Metering**: Accurate token usage and latency statistics are collected in the Python Runtime and sent back to the Go Control Plane via gRPC for auditing.
- **Distributed Tracing**: Integrated with **OpenTelemetry (SigNoz)** for cross-language (Go -> Python) performance analysis.

### 🧠 Hybrid RAG
- **Vector Search (OSS)**: High-performance retrieval based on **Qdrant**.
- **GraphRAG (Enterprise)**: Knowledge Graph construction and retrieval based on **NebulaGraph**, designed for complex reasoning tasks.

---

## 🛠️ Feature Matrix

| Feature | 🟢 Community Edition (OSS) | 🔵 Enterprise Edition (EE) |
| :--- | :--- | :--- |
| **Retrieval Model** | Vector Search (Qdrant) | **GraphRAG (Vector + Knowledge Graph)** |
| **Data Sources** | Local Files (PDF/Markdown) | **Feishu / DingTalk / Web Crawler** |
| **Doc Parsing** | Docling (OCR/Layout) | Docling + **Knowledge Extraction (NER/RE)** |
| **Deployment** | Single-node Docker Compose | **High Availability / K8s** |
| **Build System** | Standard Docker Images | **Layered Build (Core + Plugins)** |

---

## 🏗️ Architecture & Directory

```text
Chimera/
├── deploy/               # Docker Compose files (OSS & EE)
├── server/               # [Go] Control Plane
│   ├── cmd/
│   │   ├── server/       # 🟢 OSS Entrypoint
│   │   └── server-ee/    # 🔵 Enterprise Entrypoint (Plugin Injection)
│   ├── internal/core/    #    Interfaces & Registry
│   └── enterprise/       # 🔒 Closed-source Business Logic
├── runtime/              # [Python] Inference Runtime
│   ├── core/
│   │   ├── managers/     #    Business Logic (ETL, Inference)
│   │   └── connectors/   #    Base Connectors (File)
│   ├── enterprise/       # 🔒 Closed-source Plugins (Feishu, Nebula)
│   └── loader.py         #    Dynamic Plugin Loader
└── web/                  # [Vue3] Frontend
```

---

## 🚀 Quick Start

### 1. Community Edition
Ideal for individual developers or small teams. Lightweight, no Graph Database required.

```bash
cd deploy
# Starts Postgres, Redis, MinIO, Qdrant, SigNoz, Server, Runtime
docker-compose up -d
```

### 2. Enterprise Edition
For environments requiring SaaS integrations or GraphRAG. (Requires `enterprise` source code).

```bash
cd deploy
# Starts full stack (includes NebulaGraph Cluster)
# Note: Automatically uses Dockerfile.ee to build images with enterprise code
docker-compose -f docker-compose-ee.yml up -d --build
```

---

## 💻 Local Development Guide

### Python Runtime

```bash
cd runtime
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Service
# loader.py automatically detects if the 'enterprise' directory exists.
# If not found, it gracefully degrades to Core Mode.
python main.py
```
> **Note**: If you see `ℹ️ No enterprise directory found`, you are running in Community Mode.

### Go Server

```bash
cd server
# 1. Install dependencies
go mod download

# 2. Start OSS Version (Clean Mode)
go run cmd/server/main.go

# 3. Start Enterprise Version (Injected Mode)
# Prerequisite: server/enterprise directory must exist
go run cmd/server-ee/main.go
```
> **Note**: Enterprise startup logs will show `🔓 [Enterprise] Loading Feishu Plugin...`.

---

## 📈 Roadmap

| Version | Milestone | Status |
| :--- | :--- | :--- |
| **v0.4.0** | Multi-tenancy & Isolation | ✅ |
| **v0.5.0** | Docling Integration & SigNoz Observability | ✅ |
| **v0.6.0** | **Commercial Refactoring (Current)** <br> - Open Core Architecture <br> - Pluggable Connectors & Stores <br> - Physical Code Isolation | 🎉 |
| **v0.7.0** | **Memory & Permissions (Planning)** <br> - Redis Session (Long-term Memory) <br> - RBAC System | 🚧 |

## 📄 License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL v3)**.

*   **Allowed**: Free to use, modify, and learn.
*   **Obligation**: If you provide a service (SaaS) over a network using this software, you must make your modified source code available to users.
*   **Commercial License**: For closed-source commercial use or access to Enterprise Edition source code, please contact the author for authorization.

---

## 🤝 Contribution

Issues and Pull Requests are welcome! For new data source connectors, please follow the interface defined in `core/connectors/base.py`.

*   **Core Features**: Submit to `server/internal` or `runtime/core`.
*   **New Plugins**: Please open an Issue for discussion first.