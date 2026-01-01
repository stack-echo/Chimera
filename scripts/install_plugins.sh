#!/bin/bash

# 定义企业版仓库的本地路径 (根据你的实际位置修改)
ENT_REPO="../chimera-enterprise"

echo "🔌 正在安装企业级插件..."

if [ -d "$ENT_REPO" ]; then
    # 1. 复制 Python 插件
    # -r 递归, -u 更新(仅复制较新的文件), -v 显示过程
    cp -r "$ENT_REPO/runtime/enterprise/" ./runtime/enterprise/

    # 2. 复制 Go 插件
    cp -r "$ENT_REPO/server/enterprise/" ./server/enterprise/

    echo "✅ 企业版插件已注入！现在可以运行 Enterprise 模式。"
else
    echo "❌ 未找到企业版仓库: $ENT_REPO"
    echo "   请检查路径，或仅运行开源版本。"
fi