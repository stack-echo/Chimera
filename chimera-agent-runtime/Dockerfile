# ai-service/Dockerfile

# 使用轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 1. 先拷贝依赖文件 (利用 Docker 缓存层)
COPY requirements.txt .

# 2. 安装依赖
# 注意：Docling 依赖较多，可能需要安装系统级库
# 如果安装 Docling 失败，可能需要加上: RUN apt-get update && apt-get install -y libgl1-mesa-glx
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 拷贝所有代码
COPY . .

# 4. 设置环境变量
ENV PYTHONPATH=/app

# 5. 暴露端口
EXPOSE 50051

# 6. 启动命令 (指向新的入口 main.py)
CMD ["python", "main.py"]