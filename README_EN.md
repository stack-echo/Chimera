# 🦄 Chimera (v0.6.1)

> **The Observable AI Agent Platform.**
> **A Cognitive-Enhanced Multi-Agent PaaS Platform for Enterprises.**

[![License](https://img.shields.io/badge/license-AGPL%20v3-blue.svg)](LICENSE)
[![Go Report Card](https://goreportcard.com/badge/github.com/stack-echo/chimera)](https://goreportcard.com/report/github.com/stack-echo/chimera)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

[![English](https://img.shields.io/badge/-English-0077b5?style=for-the-badge)](README_EN.md)
[![中文](https://img.shields.io/badge/-中文-d52a1d?style=for-the-badge)](README.md)

Chimera is an enterprise-grade AI infrastructure based on a dual-core architecture of **Go (Control Plane)** + **Python (Inference Runtime)**.

In the **v0.6.1 (Stable Cognitive)** version, we've achieved a leap from "flat vector retrieval" to "deep cognitive reasoning." By integrating vector, graph, and full-text retrieval engines, Chimera can understand the hierarchical structure of documents and perform logical reasoning like an expert.

## ✨ v0.6.1 New Features: Cognitive Alignment

### 🧠 Three-way Hybrid Recall (3S Retrieval)
- **Semantic Layer**: High-dimensional vector search based on **Qdrant**, capturing deep contextual meanings.
- **Symbolic Layer**: Full-text retrieval based on **Elasticsearch**, solving the "entity linking" gap between colloquial queries and professional terminology.
- **Logical Layer**: Knowledge graph based on **NebulaGraph**, completing logical chains through multi-hop associations.

### 🧬 High-Performance Distributed ETL
- **Docling v2 Deep Parsing**: Supports **Tree-T** document hierarchy tree extraction, preserving Breadcrumbs path navigation.
- **Table Propositionalization**: Transforms unstructured tables into linear declarative sentences, significantly improving retrieval hit rates for complex data.
- **Gradient Disambiguation Algorithm**: Implements the $O(n)$ complexity entity alignment technology proposed by **BookRAG**, ensuring graph purity.

### 🔬 Full-Chain Whiteboxing (XAI)
- **Visual Reasoning**: Frontend real-time rendering of **ECharts knowledge topology graphs** and collapsible **Thought Chains**.
- **Full-Chain Tracing**: TraceID cross-language transmission (Go ↔ Python), supporting second-level auditing of each Agent's inputs and outputs in **SigNoz**.

### ⚡ Hardware Performance Optimization
- **GPU Computing Acceleration**: Deep adaptation to **RTX 4090/3060** (CUDA), vectorization performance improved by over 10x.
- **Large-Scale Environment Optimization**: Tuned for 128GB memory workstations, supporting high-concurrency knowledge base synchronization.

---

## 🛠️ Feature Matrix

| Feature Module | 🟢 Community Edition | 🔵 Enterprise Edition |
| :--- | :--- | :--- |
| **Retrieval Model** | Vector Retrieval (Qdrant) | **Three-way Hybrid Recall (Vector + Graph + ES)** |
| **Alignment Strategy** | None | **Symbol-Topology Asynchronous Alignment (Entity Linking)** |
| **Data Sources** | Local Files (PDF/Markdown) | **Feishu / DingTalk / Web Real-time Crawling** |
| **Re-ranking Algorithm** | Basic Cosine Sorting | **Multi-dimensional Skyline Filtering (Pareto Optimal)** |
| **Document Parsing** | Docling (Basic Mode) | **Tree-T Hierarchy Awareness + Table Propositionalization** |
| **Computing Acceleration** | CPU Execution | **CUDA GPU Acceleration (4090/3060 Adapted)** |

---

## 🏗️ Directory Structure

```text
Chimera/
├── deploy/               # Production Docker orchestration & Cloudflare Tunnel config
├── server/               # [Go] Control Plane (SaaS logic, JWT auth, Trace routing)
│   ├── cmd/server-ee/    # 🔵 Enterprise entry (supports plugin auto-injection)
│   └── internal/core/    # Core Registry interface definitions
├── runtime/              # [Python] Inference Plane (LangGraph workflows, hybrid storage)
│   ├── core/stores/      # Core vector store & ES adapters
│   ├── enterprise/       # 🔒 Private core: NebulaGraph logic, ProPEX extraction Agent
│   └── skills/           # Skyline re-ranker, Docling v2 parser
└── web/                  # [Vue3 + Arco] Frontend with knowledge graph rendering
```

---

## 🚀 Quick Start

### 1. Start Infrastructure
We recommend running on Ubuntu 22.04 native environment:
```bash
cd deploy
# Start full enterprise infrastructure (includes ES, Nebula, Qdrant, SigNoz)
./scripts/dev_infra.sh up ee
```

### 2. Start Computing Plane (Python Runtime)
```bash
cd runtime
pip install -r requirements.txt
python main.py
```
> **Tip**: After startup, seeing `✅ Nebula Space ... Schema initialized` indicates the graph engine is ready.

### 3. Start Control Plane (Go Server)
```bash
cd server
go run cmd/server-ee/main.go
```

---

## 📈 Version Evolution

| Version | Milestone | Status |
| :--- | :--- | :--- |
| **v0.5.0** | Introduced GraphRAG framework & SigNoz monitoring | ✅ |
| **v0.6.0** | **Open Core architecture refactoring**, physically isolating enterprise plugins | ✅ |
| **v0.6.1** | **Stable Cognitive Alignment**: ES three-way recall, Skyline filtering, GPU acceleration | 🎉 |
| **v0.7.0** | **Memory Enhancement (Planning)**: Long-term conversation memory based on Agentic-KGR | 🚧 |

## 📄 License

This project is open-sourced under the **GNU Affero General Public License v3.0 (AGPL v3)**.

*   **Requirement**: If you provide services (SaaS) based on this project over a network, you must open-source your modified code.
*   **Commercial License**: For closed-source commercial use, private deployment, or to obtain enterprise core code, contact `stack-echo` for authorization.

---

## 🤝 Contribution & Support

*   **Core Features**: Please submit PRs to `server/internal` or `runtime/core`.
*   **Online Demo**: [chat.stackecho.blog](https://chat.stackecho.blog) (requires exclusive Token).
*   **Runner API**: [api.stackecho.blog](https://api.stackecho.blog/api/v1).