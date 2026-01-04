#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 核心修复：这里的名称必须和 docker-compose.yml 中的左侧 key 完全一致
# 将 otel-collector 改为 signoz
BASE_SERVICES="postgres redis minio qdrant"
EE_SERVICES="nebula-metad nebula-graphd nebula-storaged"

usage() {
    echo -e "用法: $0 [command] [mode]"
    echo ""
    echo "Commands:"
    echo "  up      启动基础设施"
    echo "  down    停止并移除基础设施"
    echo ""
    echo "Modes:"
    echo "  oss     (默认) 启动开源版基础服务"
    echo "  ee      启动企业版全量服务 (含 NebulaGraph)"
    exit 1
}

COMMAND=$1
MODE=${2:-oss}

if [ -z "$COMMAND" ]; then
    usage
fi

cd deploy || { echo -e "${RED}❌ 找不到 deploy 目录${NC}"; exit 1; }

if [ "$COMMAND" == "up" ]; then
    if [ "$MODE" == "ee" ]; then
        echo -e "${BLUE}🚀 正在启动 [企业版] 基础设施...${NC}"
        # 核心修复：同时加载两个 yaml 文件，这样 ee 模式也能找到 base 服务
        docker-compose -f docker-compose.yml -f docker-compose-ee.yml up -d $BASE_SERVICES $EE_SERVICES
    else
        echo -e "${GREEN}🌱 正在启动 [开源版] 基础设施...${NC}"
        docker-compose -f docker-compose.yml up -d $BASE_SERVICES
    fi

    # 检查执行结果
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ 基础设施启动成功！${NC}"
        echo -e "👉 Postgres: :5432 | Redis: :6379 | MinIO: :9000 | Qdrant: :6333"
        [ "$MODE" == "ee" ] && echo -e "👉 Nebula: :9669"
    else
        echo -e "${RED}❌ 启动失败，请检查上方 Docker 错误信息${NC}"
        exit 1
    fi

elif [ "$COMMAND" == "down" ]; then
    echo -e "${YELLOW}🛑 正在停止所有基础设施...${NC}"
    docker-compose -f docker-compose.yml -f docker-compose-ee.yml down 2>/dev/null
    echo -e "✅ 所有服务已停止。"
else
    usage
fi

cd ..