# Build Stage
FROM node:18-alpine AS builder

WORKDIR /app

# 安装依赖
COPY package*.json ./
# 淘宝源加速 (可选)
# RUN npm config set registry https://registry.npmmirror.com
RUN npm install

# 构建
COPY . .
RUN npm run build

# Production Stage
FROM nginx:alpine

# 1. 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 2. 复制自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]