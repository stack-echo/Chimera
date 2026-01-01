#!/bin/bash

# 定义路径
CORE_ROOT=$(pwd)
ENT_REPO="../chimera-enterprise"

echo "🔧 初始化本地开发环境..."

# 1. 检查私有仓库是否存在
if [ ! -d "$ENT_REPO" ]; then
    echo "❌ 未找到兄弟目录 ../chimera-enterprise，仅配置开源环境。"
else
    echo "✅ 发现企业版仓库，正在建立软链接..."

    # Python Runtime 链接
    rm -rf runtime/enterprise # 先清理可能的空目录
    ln -s "$CORE_ROOT/$ENT_REPO/runtime/enterprise" "$CORE_ROOT/runtime/enterprise"
    echo "🔗 Python Enterprise Linked."

    # Go Server 链接
    rm -rf server/enterprise
    ln -s "$CORE_ROOT/$ENT_REPO/server/enterprise" "$CORE_ROOT/server/enterprise"
    echo "🔗 Go Enterprise Linked."
fi

echo "🎉 开发环境就绪！"
echo "👉 核心代码修改 -> 提交到 Chimera"
echo "👉 企业目录修改 -> 提交到 chimera-enterprise"