package data

import (
	"Chimera-RAG/backend-go/internal/conf"
	"context"
	"fmt"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"log"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/redis/go-redis/v9"

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
	// 1. 初始化 Redis
	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})
	if _, err := rdb.Ping(context.Background()).Result(); err != nil {
		log.Fatalf("Redis 连接失败: %v", err)
	}

	// 2. 初始化 MinIO
	minioClient, err := minio.New("localhost:9000", &minio.Options{
		Creds:  credentials.NewStaticV4("minioadmin", "minioadmin", ""),
		Secure: false,
	})
	if err != nil {
		log.Fatalf("MinIO 初始化失败: %v", err)
	}

	// 自动创建 MinIO Bucket
	bucketName := "chimera-docs"
	exists, err := minioClient.BucketExists(context.Background(), bucketName)
	if err != nil {
		log.Fatalf("检查 MinIO Bucket 失败: %v", err)
	}
	if !exists {
		err = minioClient.MakeBucket(context.Background(), bucketName, minio.MakeBucketOptions{})
		if err != nil {
			log.Fatalf("创建 MinIO Bucket 失败: %v", err)
		}
		log.Printf("🎉 MinIO Bucket '%s' 创建成功", bucketName)
	}

	// 3. 初始化 Qdrant
	qdrantClient, err := qdrant.NewClient(&qdrant.Config{
		Host: "localhost",
		Port: 6334,
	})
	if err != nil {
		log.Fatalf("无法初始化 Qdrant 客户端: %v", err)
	}

	// ⚠️ 移除了 Health() 调用，直接通过创建 Collection 来验证连接
	// 这样兼容性最好，不会因为 SDK 版本变动报错
	createCollection(qdrantClient)

	pgDB, err := NewPostgresDB(cfg)
	if err != nil {
		log.Fatalf("无法初始化 Postgres 客户端: %v", err)
	}

	d := &Data{
		Minio:  minioClient,
		Redis:  rdb,
		Qdrant: qdrantClient,
		DB:     pgDB,
	}

	// 构造清理函数
	cleanup := func() {
		log.Println("正在关闭数据层资源...")

		// 关闭 Postgres 连接
		if sqlDB, err := d.DB.DB(); err == nil {
			sqlDB.Close()
		}

		// 如果有 Redis 或 Qdrant 的 Close 方法，也在这里调用
		d.Redis.Close()
		d.Qdrant.Close()
	}

	return d, cleanup, nil
}

// 辅助函数：确保 Collection 存在
func createCollection(client *qdrant.Client) {
	ctx := context.Background()

	// 尝试列出集合，这本身就是一种连接测试
	collections, err := client.ListCollections(ctx)
	if err != nil {
		// 如果这里报错，说明 Qdrant 没连上
		log.Printf("⚠️ 无法连接 Qdrant (ListCollections 失败): %v", err)
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
				Size:     384, // ⚠️ 配合 Mock 数据，未来需改为 768
				Distance: qdrant.Distance_Cosine,
			}),
		})

		if err != nil {
			log.Printf("创建 Collection 失败: %v", err)
		} else {
			log.Println("🎉 Qdrant Collection 'chimera_docs' 创建成功")
		}
	} else {
		log.Println("🎉 Qdrant 连接成功 (Collection 'chimera_docs' 已存在)")
	}
}

// SearchSimilar 核心检索功能 (使用最新的 Query API)
func (d *Data) SearchSimilar(ctx context.Context, vector []float32, topK uint64) ([]SearchResult, error) {
	// 将 vector 转为 SDK 需要的格式
	queryVal := make([]float32, len(vector))
	copy(queryVal, vector)

	// 使用 Query 接口 (这是 Qdrant 的新标准)
	points, err := d.Qdrant.Query(ctx, &qdrant.QueryPoints{
		CollectionName: "chimera_docs",
		Query:          qdrant.NewQuery(queryVal...), // 使用 NewQuery 包装向量
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
	// 这里的配置需要在 config.yaml 里加，暂时先写死测试，或者你马上去改 config
	// dsn := "host=localhost user=chimera_user password=chimera_password dbname=chimera_db port=5432 sslmode=disable TimeZone=Asia/Shanghai"

	// 建议从 cfg 读取:
	dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=disable",
		"localhost", // 如果是 Docker 内部互联用 "postgres"，本地运行用 "localhost"
		"reg_user",
		"reg_password",
		"reg_db",
		"5432",
	)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		return nil, err
	}

	// 🔥 核心：自动迁移模式，自动创建表结构
	if err := db.AutoMigrate(
		&User{},
		&Organization{},
		&KnowledgeBase{},
		&Document{},
	); err != nil {
		return nil, fmt.Errorf("database migration failed: %v", err)
	}

	log.Println("✅ PostgreSQL connected & Schema migrated!")
	return db, nil
}
