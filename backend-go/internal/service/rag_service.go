package service

import (
	"context"
	"fmt"
	"log"
	"mime/multipart"
	"path/filepath"

	pb "Chimera-RAG/api/rag/v1"
	"Chimera-RAG/backend-go/internal/data"

	"github.com/minio/minio-go/v7"
)

// RagService 定义业务逻辑
type RagService struct {
	grpcClient pb.LLMServiceClient
	data       *data.Data
}

// NewRagService 构造函数
func NewRagService(client pb.LLMServiceClient, data *data.Data) *RagService {
	return &RagService{
		grpcClient: client,
		data:       data,
	}
}

// StreamChat 核心逻辑：调用 gRPC 并把结果推到一个 channel 里给 Handler 用
// 返回一个只读 channel，Handler 只需要从里面读字符串即可
func (s *RagService) StreamChat(ctx context.Context, req *pb.AskRequest) (<-chan string, error) {

	// 1. 创建一个管道，用于把 gRPC 的数据“搬运”给 HTTP
	// 使用带缓冲的 channel 防止阻塞
	respChan := make(chan string, 10)

	// 2. 启动协程后台搬运
	go func() {
		defer close(respChan) // 搬运结束关闭管道

		// 1. 发送 "思考中" 信号
		respChan <- "THINKing: 正在理解您的问题..."

		// 2. 调用 Python 进行 Query 向量化
		// 注意：这里我们复用 EmbedData 接口
		embResp, err := s.grpcClient.EmbedData(ctx, &pb.EmbedRequest{
			Data: &pb.EmbedRequest_Text{Text: req.Query},
		})
		if err != nil {
			respChan <- "ERR: 向量化服务异常 - " + err.Error()
			return
		}

		respChan <- fmt.Sprintf("THINKing: 意图识别完成，生成查询向量 (%d 维)...", len(embResp.Vector))

		// 3. 去 Qdrant 检索
		docs, err := s.data.SearchSimilar(ctx, embResp.Vector, 3) // 找最相似的3个
		if err != nil {
			respChan <- "ERR: 知识库检索失败 - " + err.Error()
			return
		}

		if len(docs) == 0 {
			respChan <- "ANSWER: 抱歉，知识库中没有找到相关内容。"
			return
		}

		// 4. (临时) 直接把搜到的文件名返回，证明检索成功
		// 下一步我们再接入 LLM 做润色
		respChan <- "THINKing: 已在知识库中定位到相关文档，正在整理..."

		respChan <- "ANSWER: 根据您的查询，我在知识库中找到了以下线索：\n\n"
		for i, docName := range docs {
			// 模拟打字机效果，把搜索结果打出来
			line := fmt.Sprintf("%d. 📄 来源文档: %s\n", i+1, docName)
			respChan <- "ANSWER: " + line
		}

		respChan <- "ANSWER: \n(以上是基于向量检索的真实结果，RAG 链路已跑通！)"
	}()

	return respChan, nil
}

// UploadDocument 处理文件上传业务
func (s *RagService) UploadDocument(ctx context.Context, file *multipart.FileHeader) (string, error) {
	// 1. 打开文件流
	src, err := file.Open()
	if err != nil {
		return "", err
	}
	defer src.Close()

	// 2. 生成对象名 (防止重名，这里简单用文件名，生产环境建议用 UUID)
	objectName := filepath.Base(file.Filename)
	bucketName := "chimera-docs"

	// 3. 流式上传到 MinIO (核心亮点：内存占用极低)
	info, err := s.data.Minio.PutObject(ctx, bucketName, objectName, src, file.Size, minio.PutObjectOptions{
		ContentType: "application/pdf", // 假设传的是 PDF
	})
	if err != nil {
		log.Printf("MinIO 上传失败: %v", err)
		return "", err
	}

	log.Printf("文件已存入 MinIO: %s (Size: %d)", objectName, info.Size)

	// 4. 写入 Redis 任务队列 (异步解耦)
	// 将文件名推送到 "task:parse_pdf" 队列中
	err = s.data.Redis.LPush(ctx, "task:parse_pdf", objectName).Err()
	if err != nil {
		log.Printf("Redis 推送失败: %v", err)
		return "", err
	}

	return objectName, nil
}
