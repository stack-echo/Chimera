package main

import (
	"context"
	"log"
	"time" // 引入 time 用于设置超时

	"github.com/gin-gonic/gin"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "Chimera-RAG/api/rag/v1"
	"Chimera-RAG/backend-go/internal/data"
	"Chimera-RAG/backend-go/internal/handler"
	"Chimera-RAG/backend-go/internal/service"
	"Chimera-RAG/backend-go/internal/worker"
)

func main() {
	log.Println("🔍 [1/7] 程序启动，正在尝试连接 Python gRPC...")

	// 增加超时设置，防止 gRPC 连不上一直卡着
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	conn, err := grpc.DialContext(ctx, "localhost:50051", grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithBlock())
	if err != nil {
		log.Fatalf("❌ gRPC 连接失败 (Python 服务没起?): %v", err)
	}
	defer conn.Close()
	log.Println("✅ [2/7] gRPC 连接成功")

	log.Println("🔍 [3/7] 正在初始化基础设施 (MinIO/Redis/Qdrant)...")
	dataClient := data.NewData()
	log.Println("✅ [4/7] 基础设施初始化完毕")

	grpcClient := pb.NewLLMServiceClient(conn)
	ragService := service.NewRagService(grpcClient, dataClient)
	chatHandler := handler.NewChatHandler(ragService)

	log.Println("🔍 [5/7] 正在启动后台 Worker...")
	etlWorker := worker.NewETLWorker(dataClient, grpcClient)

	// ⚠️ 重点检查这里有没有 'go'
	go etlWorker.Start(context.Background(), 3)
	log.Println("✅ [6/7] 后台 Worker 已异步启动")

	r := gin.Default()
	// ... (CORS配置省略) ...
	r.Use(func(c *gin.Context) {
		c.Next()
	})

	v1 := r.Group("/api/v1")
	{
		v1.POST("/chat/stream", chatHandler.HandleChatSSE)
		v1.POST("/upload", chatHandler.HandleUpload)
	}

	log.Println("🚀 [7/7] 准备监听 8080 端口...")
	if err := r.Run(":8080"); err != nil {
		log.Fatalf("❌ Server 启动失败: %v", err)
	}
}
