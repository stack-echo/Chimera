package main

import (
	"Chimera-RAG/backend-go/internal/middleware"
	"Chimera-RAG/backend-go/internal/repository"
	"log"

	"github.com/gin-contrib/cors" // 需执行 go get github.com/gin-contrib/cors
	"github.com/gin-gonic/gin"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "Chimera-RAG/backend-go/api/rag/v1"
	"Chimera-RAG/backend-go/internal/conf"
	"Chimera-RAG/backend-go/internal/data"
	"Chimera-RAG/backend-go/internal/handler"
	"Chimera-RAG/backend-go/internal/service"
)

func main() {
	// 1. 加载配置
	cfg := conf.LoadConfig()

	// 2. 初始化 gRPC 连接 (Python AI Service)
	// 设置 100MB 限制以支持大文件传输
	maxMsgSize := 100 * 1024 * 1024
	conn, err := grpc.NewClient(
		cfg.AI.GRPCHost,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(maxMsgSize),
			grpc.MaxCallSendMsgSize(maxMsgSize),
		),
	)
	if err != nil {
		log.Fatalf("❌ 无法连接 AI Service: %v", err)
	}
	defer conn.Close()

	// 3. 初始化数据层 (Postgres, Qdrant, Redis, MinIO)
	// 注意：这里传入 cfg 是为了让 data 层读取数据库配置
	d, cleanup, err := data.NewData(cfg)
	if err != nil {
		log.Fatalf("❌ 数据层初始化失败: %v", err)
	}
	defer cleanup()
	userRepo := repository.NewUserRepository(d.DB)

	// 4. 初始化服务层与 Worker
	grpcClient := pb.NewRagServiceClient(conn)
	ragService := service.NewRagService(grpcClient, d)
	orgService := service.NewOrgService(d)
	kbService := service.NewKBService(d)
	fileService := service.NewFileService(d)
	authService := service.NewAuthService(userRepo)

	// 5. 初始化 Handler (控制器)
	orgHandler := handler.NewOrgHandler(orgService)
	kbHandler := handler.NewKBHandler(kbService)
	fileHandler := handler.NewFileHandler(fileService)
	authHandler := handler.NewAuthHandler(authService)
	chatHandler := handler.NewChatHandler(ragService)

	// 6. 初始化 Gin Web Server
	r := gin.Default()

	// 🔥 关键：配置 CORS 跨域
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"}, // 开发环境允许所有，生产环境建议指定前端域名
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "Authorization"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
	}))

	// 7. 注册路由
	api := r.Group("/api/v1")
	{
		// 用户认证模块
		auth := api.Group("/auth")
		{
			auth.POST("/register", authHandler.Register)
			auth.POST("/login", authHandler.Login)
		}
		// 受保护的路由 (Protected Routes)
		// 使用 Use 加载中间件
		protected := api.Group("/")
		protected.Use(middleware.JWTAuth())
		{
			// 文件上传
			protected.POST("/files/upload", fileHandler.Upload)
			// 聊天
			protected.POST("/chat/stream", chatHandler.HandleChatSSE)
			// 组织
			protected.POST("/orgs", orgHandler.Create)
			protected.GET("/orgs", orgHandler.List)
			// 知识库路由
			protected.POST("/kbs", kbHandler.Create)
			protected.GET("/kbs", kbHandler.List)
		}
		protected.GET("/file/:filename", chatHandler.HandleGetFile)
	}

	log.Println("🚀 Chimera-RAG 后端已启动，监听端口 :8080")
	if err := r.Run(":8080"); err != nil {
		log.Fatalf("❌ Server 启动失败: %v", err)
	}
}
