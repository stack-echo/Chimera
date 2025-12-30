package data

import (
	"context"
	"fmt"
	"log"
	"net"
	"strconv"

	"Chimera/backend-go/internal/conf"
	"Chimera/backend-go/internal/model"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/redis/go-redis/v9"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"

	// Qdrant 官方 Go SDK
	"github.com/qdrant/go-client/qdrant"
)

// Data 结构体持有所有数据库句柄
type Data struct {
	Minio  *minio.Client
	Redis  *redis.Client
	Qdrant *qdrant.Client
	DB     *gorm.DB
}

type SearchResult struct {
	Content  string
	FileName string
	Page     int32
}

func NewData(cfg *conf.Config) (*Data, func(), error) {
	// 1. 连接 Postgres
	dsn := cfg.Data.DatabaseSource
	pgDB, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		return nil, nil, fmt.Errorf("failed to open database: %v", err)
	}

	// 🔥🔥🔥 核心：在此处执行自动迁移 🔥🔥🔥
	// 将所有新定义的 struct 都放进来，GORM 会自动建表或修改字段
	if err := pgDB.AutoMigrate(
		&model.User{},
		&model.Organization{},
		&model.OrganizationMember{}, // 权限表
		&model.KnowledgeBase{},      // 知识库容器
		&model.DataSource{},         // 数据源 (替代原来的 Document)
		&model.Application{},        // 智能体应用
		&model.AppRunLog{},          // 监控日志
	); err != nil {
		return nil, nil, fmt.Errorf("schema migration failed: %v", err)
	}

	fmt.Println("✅ 数据库表结构迁移完成")

	// -------------------------------------------------------
	// 1. 初始化 Redis
	// -------------------------------------------------------
	rdb := redis.NewClient(&redis.Options{
		Addr:     cfg.Data.RedisAddr,     // 从配置读取 "localhost:6379"
		Password: cfg.Data.RedisPassword, // 🔥 从配置读取 "chimera_secret"
	})
	if _, err := rdb.Ping(context.Background()).Result(); err != nil {
		log.Fatalf("❌ Redis 连接失败: %v", err)
	}
	log.Println("✅ Redis 连接成功")

	// -------------------------------------------------------
	// 2. 初始化 MinIO
	// -------------------------------------------------------
	minioClient, err := minio.New(cfg.Data.MinioEndpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.Data.MinioAccessKey, cfg.Data.MinioSecretKey, ""),
		Secure: false,
	})
	if err != nil {
		log.Fatalf("❌ MinIO 初始化失败: %v", err)
	}

	// 自动创建 MinIO Bucket
	bucketName := cfg.Data.MinioBucket // 从配置读取 "chimera-docs"
	if bucketName == "" {
		bucketName = "chimera-docs" // 兜底
	}

	exists, err := minioClient.BucketExists(context.Background(), bucketName)
	if err != nil {
		log.Fatalf("❌ 检查 MinIO Bucket 失败: %v", err)
	}
	if !exists {
		err = minioClient.MakeBucket(context.Background(), bucketName, minio.MakeBucketOptions{})
		if err != nil {
			log.Fatalf("❌ 创建 MinIO Bucket 失败: %v", err)
		}
		log.Printf("🎉 MinIO Bucket '%s' 创建成功", bucketName)
	} else {
		log.Printf("✅ MinIO 连接成功 (Bucket '%s' 已存在)", bucketName)
	}

	// -------------------------------------------------------
	// 3. 初始化 Qdrant
	// -------------------------------------------------------
	// 解析 Qdrant 地址 (cfg 中是 "localhost:6334")
	qdrantHost, qdrantPort := parseHostPort(cfg.Data.QdrantAddr, "localhost", 6334)

	qdrantClient, err := qdrant.NewClient(&qdrant.Config{
		Host: qdrantHost,
		Port: qdrantPort,
	})
	if err != nil {
		log.Fatalf("❌ 无法初始化 Qdrant 客户端: %v", err)
	}

	// 验证连接并创建集合
	createCollection(qdrantClient)

	d := &Data{
		Minio:  minioClient,
		Redis:  rdb,
		Qdrant: qdrantClient,
		DB:     pgDB,
	}

	// 构造清理函数
	cleanup := func() {
		log.Println("正在关闭数据层资源...")
		if sqlDB, err := d.DB.DB(); err == nil {
			sqlDB.Close()
		}
		d.Redis.Close()
		d.Qdrant.Close()
	}

	return d, cleanup, nil
}

// 辅助函数: 解析 "host:port" 字符串
func parseHostPort(addr string, defaultHost string, defaultPort int) (string, int) {
	host, portStr, err := net.SplitHostPort(addr)
	if err != nil {
		return defaultHost, defaultPort
	}
	port, err := strconv.Atoi(portStr)
	if err != nil {
		return host, defaultPort
	}
	return host, port
}

// 辅助函数：确保 Collection 存在
func createCollection(client *qdrant.Client) {
	ctx := context.Background()

	// 尝试列出集合，这本身就是一种连接测试
	collections, err := client.ListCollections(ctx)
	if err != nil {
		log.Printf("⚠️ 无法连接 Qdrant (ListCollections 失败): %v", err)
		// 这里不 Fatal，防止向量库挂了影响主程序启动，但生产环境建议处理
		return
	}

	exists := false
	for _, c := range collections {
		if c == "chimera_docs" {
			exists = true
			break
		}
	}

	if !exists {
		// 创建向量集合
		err := client.CreateCollection(ctx, &qdrant.CreateCollection{
			CollectionName: "chimera_docs",
			VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
				Size:     384, // ⚠️ 注意: 这里的维度必须和 Python embedding 模型一致 (all-MiniLM-L6-v2 是 384)
				Distance: qdrant.Distance_Cosine,
			}),
		})

		if err != nil {
			log.Printf("❌ 创建 Collection 失败: %v", err)
		} else {
			log.Println("🎉 Qdrant Collection 'chimera_docs' 创建成功")
		}
	} else {
		log.Println("✅ Qdrant 连接成功 (Collection 'chimera_docs' 已存在)")
	}
}

// SearchSimilar 核心检索功能
func (d *Data) SearchSimilar(ctx context.Context, vector []float32, topK uint64) ([]SearchResult, error) {
	queryVal := make([]float32, len(vector))
	copy(queryVal, vector)

	points, err := d.Qdrant.Query(ctx, &qdrant.QueryPoints{
		CollectionName: "chimera_docs",
		Query:          qdrant.NewQuery(queryVal...),
		Limit:          &topK,
		WithPayload: &qdrant.WithPayloadSelector{
			SelectorOptions: &qdrant.WithPayloadSelector_Enable{
				Enable: true,
			},
		},
	})
	if err != nil {
		return nil, err
	}

	var results []SearchResult
	for _, point := range points {
		res := SearchResult{}
		if val, ok := point.Payload["content"]; ok {
			res.Content = val.GetStringValue()
		}
		if val, ok := point.Payload["filename"]; ok {
			res.FileName = val.GetStringValue()
		}
		if val, ok := point.Payload["page_number"]; ok {
			res.Page = int32(val.GetIntegerValue())
		}
		results = append(results, res)
	}
	return results, nil
}

// NewPostgresDB 初始化 PG 连接
func NewPostgresDB(cfg *conf.Config) (*gorm.DB, error) {
	// 🔥 核心修改：不再使用硬编码，而是使用 cfg 中的配置
	// 这里的 cfg.Data.DatabaseSource 已经在 config.go 中设置了默认值:
	// "postgres://chimera_user:chimera_secret@localhost:5432/chimera_main?sslmode=disable"
	dsn := cfg.Data.DatabaseSource

	log.Printf("正在连接数据库...") // 不要打印 DSN，防止密码泄露

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		return nil, err
	}

	// 🔥 核心：自动迁移模式，自动创建表结构 (v0.4.0 Schema)
	if err := db.AutoMigrate(
		&model.User{},
		&model.Organization{},
		&model.OrganizationMember{},
		&model.KnowledgeBase{},
		&model.DataSource{},
	); err != nil {
		return nil, fmt.Errorf("database migration failed: %v", err)
	}

	log.Println("✅ PostgreSQL 连接成功 & 表结构已迁移!")
	return db, nil
}
