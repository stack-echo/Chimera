# runtime/Dockerfile (Core)
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 🔥 只复制 Core 代码 (利用 .dockerignore 排除 enterprise 目录)
COPY . .

ENV PYTHONPATH=/app
EXPOSE 50051
CMD ["python", "main.py"]