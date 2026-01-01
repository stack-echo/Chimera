# server/Dockerfile (Core)
FROM golang:1.24-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
ENV GOPROXY=https://goproxy.cn,direct
RUN go mod download

COPY . .
# 🔥 编译开源入口
RUN go build -o server cmd/server/main.go

FROM alpine:latest
WORKDIR /app
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /app/server .
EXPOSE 8080
CMD ["./server"]