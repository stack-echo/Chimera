package conf

import (
	"log"

	"github.com/spf13/viper"
)

type Config struct {
	App  AppConfig
	Data DataConfig
	AI   AIConfig
}

type AppConfig struct {
	Port string
}

type DataConfig struct {
	// --- 新增: 数据库配置 (Postgres) ---
	DatabaseDriver string
	DatabaseSource string // 连接字符串 (DSN)

	// --- Redis ---
	RedisAddr     string
	RedisPassword string // 新增: 密码字段

	// --- MinIO ---
	MinioEndpoint  string
	MinioAccessKey string
	MinioSecretKey string
	MinioBucket    string // 建议把 Bucket 名也配进来

	// --- Qdrant ---
	QdrantAddr string
}

type AIConfig struct {
	GRPCHost string
}

func LoadConfig() *Config {
	v := viper.New()

	// ==========================================
	// 1. 设置默认值 (对应 docker-compose.yml)
	// ==========================================

	// App
	v.SetDefault("APP_PORT", "8080")

	// Postgres (新)
	// 格式: postgres://user:password@host:port/dbname?sslmode=disable
	v.SetDefault("DATA_DB_DRIVER", "postgres")
	v.SetDefault("DATA_DB_SOURCE", "postgres://chimera_user:chimera_secret@localhost:25432/chimera_main?sslmode=disable")

	// Redis (新密码)
	v.SetDefault("DATA_REDIS_ADDR", "localhost:6379")
	v.SetDefault("DATA_REDIS_PASSWORD", "chimera_secret") // 对应 docker command --requirepass

	// MinIO (新凭证)
	v.SetDefault("DATA_MINIO_ENDPOINT", "localhost:9000")
	v.SetDefault("DATA_MINIO_AK", "chimera_minio")        // 对应 MINIO_ROOT_USER
	v.SetDefault("DATA_MINIO_SK", "chimera_minio_secret") // 对应 MINIO_ROOT_PASSWORD
	v.SetDefault("DATA_MINIO_BUCKET", "chimera-docs")     // 默认 Bucket

	// Qdrant
	v.SetDefault("DATA_QDRANT_ADDR", "localhost:6334")

	// AI Service
	v.SetDefault("AI_GRPC_HOST", "localhost:50051")

	// ==========================================
	// 2. 读取配置
	// ==========================================

	// 允许读取环境变量 (自动将 . 转换为 _)
	v.AutomaticEnv()

	// 读取本地 .env 文件 (可选)
	v.SetConfigName(".env")
	v.SetConfigType("env")
	v.AddConfigPath(".")
	_ = v.ReadInConfig()

	var c Config

	// ==========================================
	// 3. 映射到结构体
	// ==========================================

	c.App.Port = v.GetString("APP_PORT")

	// Data - DB
	c.Data.DatabaseDriver = v.GetString("DATA_DB_DRIVER")
	c.Data.DatabaseSource = v.GetString("DATA_DB_SOURCE")

	// Data - Redis
	c.Data.RedisAddr = v.GetString("DATA_REDIS_ADDR")
	c.Data.RedisPassword = v.GetString("DATA_REDIS_PASSWORD")

	// Data - MinIO
	c.Data.MinioEndpoint = v.GetString("DATA_MINIO_ENDPOINT")
	c.Data.MinioAccessKey = v.GetString("DATA_MINIO_AK")
	c.Data.MinioSecretKey = v.GetString("DATA_MINIO_SK")
	c.Data.MinioBucket = v.GetString("DATA_MINIO_BUCKET")

	// Data - Qdrant
	c.Data.QdrantAddr = v.GetString("DATA_QDRANT_ADDR")

	// AI
	c.AI.GRPCHost = v.GetString("AI_GRPC_HOST")

	log.Println("✅ 配置加载完成 (适配 v0.4.0 环境)")
	return &c
}
