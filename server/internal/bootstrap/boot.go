package bootstrap

import (
	"log"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	// 引入 PB 和 Internal 模块
	pb "Chimera/server/api/runtime/v1"
	"Chimera/server/internal/conf"
	"Chimera/server/internal/data"
	"Chimera/server/internal/handler"
	"Chimera/server/internal/middleware"
	"Chimera/server/internal/repository"
	"Chimera/server/internal/service"
)

// Run 启动服务器
func Run() {
	// 1. 加载配置
	cfg := conf.LoadConfig()

	// 2. 初始化 gRPC 连接 (Python AI Service)
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

	// 3. 初始化数据层
	d, cleanup, err := data.NewData(cfg)
	if err != nil {
		log.Fatalf("❌ 数据层初始化失败: %v", err)
	}
	defer cleanup()

	userRepo := repository.NewUserRepository(d.DB)

	// 4. 初始化服务层 (Service & Adapter)
	grpcClient := pb.NewRuntimeServiceClient(conn)
	adapter := service.NewRuntimeAdapter(grpcClient)

	// ChatService (原 RuntimeService)
	chatSvc := service.NewChatService(d, adapter)
	// DataSourceService (新拆分)
	dsSvc := service.NewDataSourceService(d, adapter)

	// 其他基础服务
	orgSvc := service.NewOrgService(d)
	kbSvc := service.NewKBService(d)
	authSvc := service.NewAuthService(userRepo)
	logSvc := service.NewLogService(d)

	// 5. 初始化 Handler
	orgH := handler.NewOrgHandler(orgSvc)
	kbH := handler.NewKBHandler(kbSvc)
	authH := handler.NewAuthHandler(authSvc)
	logH := handler.NewLogHandler(logSvc)
	chatH := handler.NewChatHandler(chatSvc) // 只负责对话

	dsH := handler.NewDataSourceHandler(dsSvc) // 负责数据源
	fileH := handler.NewFileHandler(dsSvc)     // 负责文件

	// 6. 初始化 Gin Server
	r := gin.Default()
	r.Use(middleware.TraceMiddleware())

	// CORS 配置
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "Content-Length", "Accept-Encoding", "X-CSRF-Token", "Authorization"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))

	// 7. 注册路由
	api := r.Group("/api/v1")
	{
		// 公开接口
		auth := api.Group("/auth")
		{
			auth.POST("/register", authH.Register)
			auth.POST("/login", authH.Login)
		}

		// 鉴权接口
		protected := api.Group("/")
		protected.Use(middleware.JWTAuth())
		{
			// 文件上传 (调用 FileHandler)
			protected.POST("/files/upload", fileH.Upload)
			// 对话流 (调用 ChatHandler)
			protected.POST("/chat/stream", chatH.HandleChatSSE)
			// 数据源创建 (调用 DataSourceHandler)
			protected.POST("/datasources", dsH.Create)

			// 组织与知识库
			protected.POST("/orgs", orgH.Create)
			protected.GET("/orgs", orgH.List)
			protected.POST("/kbs", kbH.Create)
			protected.GET("/kbs", kbH.List)

			// 监控
			protected.GET("/logs", logH.List)
			protected.GET("/stats", logH.Stats)
		}

		// 文件下载
		protected.GET("/file/:filename", fileH.HandleGetFile)
	}

	log.Println("🚀 Chimera 后端已启动，监听端口 :8080")
	if err := r.Run(":8082"); err != nil {
		log.Fatalf("❌ Server 启动失败: %v", err)
	}
}
