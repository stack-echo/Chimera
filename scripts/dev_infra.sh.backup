#!/bin/bash

# ========================================================
# Chimera 本地开发基础设施启动脚本
# 用途: 仅启动数据库、缓存等依赖服务，不启动 Server/Runtime 应用
# ========================================================

# 定义颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 基础服务列表 (OSS & EE 通用)
# 注意：这里使用的是 docker-compose.yml 中的 service name
BASE_SERVICES="postgres redis minio qdrant otel-collector"

# 企业版专属服务 (NebulaGraph 集群)
EE_SERVICES="nebula-metad nebula-graphd nebula-storaged"

# 帮助信息
usage() {
    echo -e "用法: $0 [command] [mode]"
    echo ""
    echo "Commands:"
    echo "  up      启动基础设施"
    echo "  down    停止并移除基础设施"
    echo ""
    echo "Modes:"
    echo "  oss     (默认) 启动开源版基础服务 (PG, Redis, MinIO, Qdrant)"
    echo "  ee      启动企业版全量服务 (包含 NebulaGraph)"
    echo ""
    echo "示例:"
    echo "  $0 up oss    # 启动开源版资源"
    echo "  $0 up ee     # 启动企业版资源"
    echo "  $0 down      # 关闭所有资源"
    exit 1
}

# 检查参数
COMMAND=$1
MODE=${2:-oss} # 默认为 oss

if [ -z "$COMMAND" ]; then
    usage
fi

# 进入 deploy 目录 (确保 docker-compose 上下文正确)
cd deploy || { echo "❌ 找不到 deploy 目录，请在项目根目录运行此脚本"; exit 1; }

# =======================
# 启动逻辑 (UP)
# =======================
if [ "$COMMAND" == "up" ]; then
    if [ "$MODE" == "ee" ]; then
        echo -e "${BLUE}🚀 正在启动 [企业版] 基础设施...${NC}"
        echo -e "${YELLOW}包含服务: $BASE_SERVICES $EE_SERVICES${NC}"

        # 使用 EE 配置文件，指定启动具体的 Service，忽略 server/runtime/web
        docker-compose -f docker-compose-ee.yml up -d $BASE_SERVICES $EE_SERVICES

    else
        echo -e "${GREEN}🌱 正在启动 [开源版] 基础设施...${NC}"
        echo -e "${YELLOW}包含服务: $BASE_SERVICES${NC}"

        # 使用 OSS 配置文件
        docker-compose -f docker-compose.yml up -d $BASE_SERVICES
    fi

    echo ""
    echo -e "✅ 基础设施启动完毕！"
    echo -e "👉 Postgres: :5432"
    echo -e "👉 Redis:    :6379"
    echo -e "👉 MinIO:    :9000 (Console :9001)"
    echo -e "👉 Qdrant:   :6333"
    if [ "$MODE" == "ee" ]; then
        echo -e "👉 Nebula:   :9669"
    fi

# =======================
# 停止逻辑 (DOWN)
# =======================
elif [ "$COMMAND" == "down" ]; then
    echo -e "${YELLOW}🛑 正在停止所有基础设施...${NC}"

    # 尝试停止两个配置文件定义的所有容器
    docker-compose -f docker-compose-ee.yml down 2>/dev/null
    docker-compose -f docker-compose.yml down 2>/dev/null

    echo -e "✅ 所有服务已停止。"

else
    usage
fi

# 回到原目录
cd ..