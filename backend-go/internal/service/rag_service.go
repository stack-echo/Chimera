package service

import (
	"context"
	"github.com/minio/minio-go/v7"
	"io"
	"log"
	"mime/multipart"
	"path/filepath"
	"strings"

	pb "Chimera-RAG/backend-go/api/rag/v1"
	"Chimera-RAG/backend-go/internal/data"
	"Chimera-RAG/backend-go/internal/dto"
	"Chimera-RAG/backend-go/internal/model"
)

// RagService 定义业务逻辑
type RagService struct {
	grpcClient pb.RagServiceClient
	Data       *data.Data
}

// NewRagService 构造函数
func NewRagService(client pb.RagServiceClient, data *data.Data) *RagService {
	return &RagService{
		grpcClient: client,
		Data:       data,
	}
}

// StreamChat 处理聊天请求 (v0.4.0 瘦身版)
// Go 只需要做一个“传话筒”，把 HTTP 请求参数转发给 gRPC
func (s *RagService) StreamChat(ctx context.Context, userID uint, req dto.ChatReq, respChan chan<- string) {
	defer close(respChan)
	// =================================================================
	// 🛡️ 步骤 0: 安全安检 (Security Check)
	// 在调用 Python 之前，先检查这个用户有没有资格访问这个 KB
	// =================================================================

	// 如果指定了知识库 ID (如果 KbID 为 0，可能是纯闲聊，跳过校验)
	if req.KbID > 0 {
		var kb model.KnowledgeBase
		// 1. 查询知识库是否存在
		// 假设 s.Data.DB 是你的 GORM 实例
		if err := s.Data.DB.First(&kb, req.KbID).Error; err != nil {
			log.Printf("⚠️ 知识库不存在: %v", req.KbID)
			respChan <- "ERR: 知识库不存在或已被删除"
			return
		}

		// 2. 权限判断
		if kb.OrgID != nil {
			// [组织知识库逻辑]
			var count int64
			// 注意：这里查询条件里要用 *kb.OrgID 取出实际的值
			s.Data.DB.Model(&model.OrganizationMember{}).
				Where("user_id = ? AND organization_id = ?", userID, *kb.OrgID). // 👈 加了 * 号
				Count(&count)

			if count == 0 {
				// 为了日志好看，这里也用 *kb.OrgID
				log.Printf("🚨 越权警告: 用户 %d -> 组织 %d", userID, *kb.OrgID)
				respChan <- "ERR: ⛔️ 无权访问：你不是该组织的成员"
				return
			}
		} else {
			// [个人知识库逻辑] (OrgID == nil)
			// 如果你的逻辑是“如果不属于组织，必须是自己的”，可以在这里校验
			// if kb.UserID != userID { ... }
		}
	}

	// =================================================================
	// ✅ 步骤 1: 构造 gRPC 请求 (安检通过，放行)
	// =================================================================
	// 1. 构造 gRPC 请求
	// 这里不再调用 EmbedData，而是直接把 KbID/OrgID 传给 Python
	grpcReq := &pb.ChatRequest{
		Query:     req.Query,
		SessionId: req.SessionID,    // 如果有的话
		KbId:      int64(req.KbID),  // 🔥 核心：传过去让 Python 知道查哪个库
		OrgId:     int64(req.OrgID), // 🔥 核心：传过去让 Python 知道查哪个组织
		// History: ... (如果做了历史记录转换，在这里赋值)
	}

	// 2. 调用 Python 的 ChatStream
	// 这一步之后，Python 会自动完成 Embedding -> Search -> LLM
	stream, err := s.grpcClient.ChatStream(ctx, grpcReq)
	if err != nil {
		log.Printf("❌ gRPC 调用失败: %v", err)
		respChan <- "ERR: 服务端连接失败"
		return
	}

	// 3. 转发流式响应
	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			// 流结束
			break
		}
		if err != nil {
			log.Printf("❌ gRPC 流读取错误: %v", err)
			respChan <- "ERR: 生成中断"
			return
		}

		// 将 Python 返回的文本片段发送给 HTTP 前端
		respChan <- resp.AnswerDelta
	}
}

// UploadDocument 处理文件上传全流程
func (s *RagService) UploadDocument(ctx context.Context, fileHeader *multipart.FileHeader, userID uint) (*model.Document, error) {
	// 1. 打开文件流
	src, err := fileHeader.Open()
	if err != nil {
		return nil, err
	}
	defer src.Close()

	// 2. [Data层] 上传到 MinIO
	// Service 层不需要知道 MinIO SDK 的细节，只需要给文件流
	storagePath, err := s.Data.UploadFile(ctx, src, fileHeader.Size, fileHeader.Filename)
	if err != nil {
		return nil, err
	}

	// 3. [Data层] 写入数据库 (v0.2.0 文件确权)
	doc := &model.Document{
		Title:           fileHeader.Filename,
		FileName:        fileHeader.Filename,
		FileSize:        fileHeader.Size,
		FileType:        strings.ToLower(filepath.Ext(fileHeader.Filename)), // 简单的后缀判断工具函数
		StoragePath:     storagePath,
		KnowledgeBaseID: 0, // 默认归属根目录，后续可传参
		OwnerID:         userID,
		Status:          "pending",
	}

	if err := s.Data.CreateDocument(ctx, doc); err != nil {
		// ⚠️ 进阶思考: 如果数据库写入失败，最好把 MinIO 里的垃圾文件删掉 (补偿机制)
		// s.Data.DeleteFile(ctx, storagePath)
		return nil, err
	}

	// 4. [Data层] 写入 Redis 任务队列
	// 传递 Document ID 而不是路径，Worker 可以根据 ID 查库获取更多信息
	// 也可以传 JSON: {"doc_id": 1, "path": "xxx.pdf"}
	err = s.Data.PushTask(ctx, "task:parse_pdf", storagePath)
	if err != nil {
		// 同样，如果队列失败，考虑是否回滚数据库状态为 "failed"
		return nil, err
	}

	return doc, nil
}

// GetFile 获取文件流用于预览
func (s *RagService) GetFile(ctx context.Context, fileName string) (*minio.Object, int64, error) {
	// 这里硬编码 bucket 名，或者从 s.conf 读取
	bucketName := "chimera-docs"

	// 调用 Data 层
	return s.Data.GetFileStream(ctx, bucketName, fileName)
}
