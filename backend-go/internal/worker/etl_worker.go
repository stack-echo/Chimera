package worker

import (
	"context"
	"log"
	"time"

	pb "Chimera-RAG/api/rag/v1"
	"Chimera-RAG/backend-go/internal/data"

	"github.com/google/uuid"
	"github.com/minio/minio-go/v7"
	"github.com/qdrant/go-client/qdrant"
)

// ETLWorker 负责从 Redis 拿任务，并执行 ETL 流程
type ETLWorker struct {
	data       *data.Data
	grpcClient pb.LLMServiceClient
}

func NewETLWorker(data *data.Data, client pb.LLMServiceClient) *ETLWorker {
	return &ETLWorker{
		data:       data,
		grpcClient: client,
	}
}

// Start 启动 Worker (阻塞运行)
func (w *ETLWorker) Start(ctx context.Context, numWorkers int) {
	log.Printf("🚀 启动 %d 个 ETL Worker，开始监听队列 task:parse_pdf...", numWorkers)

	for i := 0; i < numWorkers; i++ {
		go w.processLoop(ctx, i)
	}
}

func (w *ETLWorker) processLoop(ctx context.Context, workerID int) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
			// 1. 阻塞式获取任务 (BLPOP)
			result, err := w.data.Redis.BLPop(ctx, 0*time.Second, "task:parse_pdf").Result()
			if err != nil {
				// Redis 偶尔连接超时是正常的，不要 panic
				log.Printf("[Worker-%d] 等待任务中... (%v)", workerID, err)
				time.Sleep(3 * time.Second)
				continue
			}

			fileName := result[1]
			log.Printf("[Worker-%d] 收到任务: %s", workerID, fileName)

			// 2. 执行具体处理逻辑
			err = w.processFile(ctx, fileName)
			if err != nil {
				log.Printf("[Worker-%d] ❌ 处理失败: %s, 错误: %v", workerID, fileName, err)
			} else {
				log.Printf("[Worker-%d] ✅ 处理完成: %s", workerID, fileName)
			}
		}
	}
}

// processFile 单个文件的 ETL 流程
func (w *ETLWorker) processFile(ctx context.Context, fileName string) error {
	// A. 从 MinIO 获取文件流
	obj, err := w.data.Minio.GetObject(ctx, "chimera-docs", fileName, minio.GetObjectOptions{})
	if err != nil {
		return err
	}
	defer obj.Close()

	// B. 模拟解析文本
	fakeContent := "这是从文件 " + fileName + " 解析出来的模拟文本内容。"

	// C. 调用 gRPC (Python) 进行向量化
	embResp, err := w.grpcClient.EmbedData(ctx, &pb.EmbedRequest{
		Data: &pb.EmbedRequest_Text{Text: fakeContent},
	})
	if err != nil {
		return err
	}

	// D. 存入 Qdrant (适配 V1 SDK 写法)
	pointID := uuid.New().String()

	// 构造 Point (数据点)
	// 新版 SDK 对 Value 类型的封装略有不同
	payloadMap := map[string]interface{}{
		"filename": fileName,
	}

	// 构造 Upsert 请求
	upsertPoints := []*qdrant.PointStruct{
		{
			Id:      qdrant.NewIDUUID(pointID),            // 辅助函数：UUID 转 ID
			Vectors: qdrant.NewVectors(embResp.Vector...), // 辅助函数：切片转 Vector
			Payload: qdrant.NewValueMap(payloadMap),       // 辅助函数：Map 转 Payload
		},
	}

	_, err = w.data.Qdrant.Upsert(ctx, &qdrant.UpsertPoints{
		CollectionName: "chimera_docs",
		Points:         upsertPoints,
	})

	if err != nil {
		log.Printf("❌ Qdrant 写入失败: %v", err)
		return err
	}

	log.Printf("✅ 已存入 Qdrant: %s (ID: %s)", fileName, pointID)
	return nil
}
