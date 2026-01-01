.PHONY: proto-go proto-py gen

# Go 代码生成
proto-go:
	@echo "🚀 Generating Go Proto..."
	protoc --proto_path=. \
		--go_out=. --go_opt=module=Chimera \
		--go-grpc_out=. --go-grpc_opt=module=Chimera \
		api/runtime/v1/runtime.proto

# Python 代码生成
proto-py:
	@echo "🚀 Generating Python Proto..."
	mkdir -p runtime/rpc
	# 注意这里 -I 指向了 api/runtime/v1，这样生成的文件就在根目录下
	python3 -m grpc_tools.protoc \
		-Iapi/runtime/v1 \
		--python_out=runtime/rpc \
		--grpc_python_out=runtime/rpc \
		runtime.proto
	# 修复 Python 相对导入 (Mac syntax: sed -i '')
	sed -i '' 's/^import runtime_pb2/from . import runtime_pb2/' runtime/rpc/runtime_pb2_grpc.py
	# 确保是 Python 包
	touch runtime/rpc/__init__.py

# 一键生成所有
gen: proto-go proto-py
	@echo "✅ All Proto files generated successfully!"