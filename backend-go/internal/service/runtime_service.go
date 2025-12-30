package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"gorm.io/datatypes"
	"io"
	"log"
	"mime/multipart"
	"path/filepath"
	"strings"
	"time"

	// ⚠️ 注意：请根据你的 go.mod 确认这里是 "Chimera-RAG" 还是 "Chimera"
	pb "Chimera/backend-go/api/runtime/v1"
	"Chimera/backend-go/internal/data"
	"Chimera/backend-go/internal/dto"
	"Chimera/backend-go/internal/model"

	"github.com/minio/minio-go/v7"
)

// RuntimeService 核心业务逻辑层
type RuntimeService struct {
	grpcClient pb.RuntimeServiceClient
	Data       *data.Data
}

// NewRuntimeService 构造函数
func NewRuntimeService(client pb.RuntimeServiceClient, data *data.Data) *RuntimeService {
	return &RuntimeService{
		grpcClient: client,
		Data:       data,
	}
}

// StreamChat 处理聊天请求
// 负责鉴权、构造配置、调用 Python 流式接口、转发结果
func (s *RuntimeService) StreamChat(ctx context.Context, userID uint, req dto.ChatReq, respChan chan<- string) {
	defer close(respChan)

	// =================================================================
	// 🛡️ 步骤 0: 安全安检 (Security Check)
	// =================================================================
	if req.KbID > 0 {
		var kb model.KnowledgeBase
		if err := s.Data.DB.First(&kb, req.KbID).Error; err != nil {
			log.Printf("⚠️ 知识库不存在: %v", req.KbID)
			respChan <- "ERR: 知识库不存在或已被删除"
			return
		}

		// 权限判断 (组织库)
		if kb.OrgID != nil {
			var count int64
			s.Data.DB.Model(&model.OrganizationMember{}).
				Where("user_id = ? AND organization_id = ?", userID, kb.OrgID).
				Count(&count)

			if count == 0 {
				log.Printf("🚨 越权警告: 用户 %d -> 组织 %d", userID, kb.OrgID)
				respChan <- "ERR: ⛔️ 无权访问：你不是该组织的成员"
				return
			}
		}
	}

	// =================================================================
	// ✅ 步骤 1: 构造 gRPC 请求
	// =================================================================

	// 1. 构造 AppConfig
	configData := map[string]interface{}{
		"kb_ids": []uint{req.KbID}, // 传递知识库 ID 列表
		"org_id": req.OrgID,
	}
	configBytes, _ := json.Marshal(configData)

	// 2. 构造 RunAgentRequest
	grpcReq := &pb.RunAgentRequest{
		AppId:         "default_chat_app", // 后续可从 req.AppID 获取
		Query:         req.Query,
		SessionId:     req.SessionID,
		AppConfigJson: string(configBytes), // 注入配置
	}

	// =================================================================
	// 🚀 步骤 2: 调用 Python Runtime
	// =================================================================

	stream, err := s.grpcClient.RunAgent(ctx, grpcReq)
	if err != nil {
		log.Printf("❌ gRPC 调用失败: %v", err)
		respChan <- "ERR: 服务端连接失败"
		return
	}

	// =================================================================
	// 🔄 步骤 3: 转发流式响应
	// =================================================================
	// 用于拼接完整答案，存入日志
	var fullAnswerBuilder strings.Builder

	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			break // 流结束
		}
		if err != nil {
			log.Printf("❌ gRPC 流读取错误: %v", err)
			// 只有在没发过任何数据时才发错误，避免前端 JSON 解析裂开
			// 这里简单处理，直接断开
			return
		}

		// 根据 Type 分发内容
		switch resp.Type {
		case "delta":
			// 只有答案片段才推给前端
			respChan <- resp.Payload
		case "thought":
			// 思考过程 (可以在日志看，或者协议支持 SSE event: thought)
			log.Printf("🤔 [Thought]: %s", resp.Payload)
		case "summary":
			// 🔥 核心：收到 Summary，说明 Python 执行完毕，准备落库
			log.Printf("📊 收到执行报告: Tokens=%d, Time=%dms", resp.Summary.TotalTokens, resp.Summary.TotalDurationMs)
			// 异步写入数据库，不阻塞本次请求最后的响应
			go s.saveRunLog(userID, req, resp.Summary, fullAnswerBuilder.String())
		case "error":
			log.Printf("❌ [Agent Error]: %s", resp.Payload)
			respChan <- fmt.Sprintf("\n[系统错误]: %s", resp.Payload)
		}
	}
}

// 辅助方法：保存日志
func (s *RuntimeService) saveRunLog(userID uint, req dto.ChatReq, summary *pb.RunSummary, answer string) {
	// 创建一个新的 Background Context，防止因请求取消导致写入失败
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	runLog := &model.AppRunLog{
		OrgID:            req.OrgID,
		AppID:            "default_chat_app", // 暂时写死
		UserID:           userID,
		SessionID:        req.SessionID,
		Query:            req.Query,
		Answer:           answer,
		TotalTokens:      int(summary.TotalTokens),
		PromptTokens:     int(summary.PromptTokens),
		CompletionTokens: int(summary.CompletionTokens),
		DurationMs:       summary.TotalDurationMs,
		Status:           summary.FinalStatus,
	}

	if err := s.Data.DB.WithContext(ctx).Create(runLog).Error; err != nil {
		log.Printf("❌ 日志入库失败: %v", err)
	} else {
		log.Printf("✅ 日志已入库 (ID: %d)", runLog.ID)
	}
}

// UploadDocument 处理文件上传全流程 (上传 -> 落库 -> 触发同步)
func (s *RuntimeService) UploadDocument(ctx context.Context, fileHeader *multipart.FileHeader, userID uint, kbID uint) (*model.DataSource, error) {
	// =================================================================
	// 🛡️ 步骤 0: 权限鉴权 (Security Check)
	// =================================================================
	var kb model.KnowledgeBase
	// 1. 检查知识库是否存在
	if err := s.Data.DB.First(&kb, kbID).Error; err != nil {
		return nil, errors.New("知识库不存在或已被删除")
	}

	// 2. 检查是否有写入权限
	if kb.OrgID != nil {
		// --- A. 组织库鉴权 ---
		// 必须是该组织的成员 (Owner/Admin/Member 均可上传，或者你可以限制只有 Admin 可上传)
		var count int64
		s.Data.DB.Model(&model.OrganizationMember{}).
			Where("organization_id = ? AND user_id = ?", kb.OrgID, userID).
			Count(&count)

		if count == 0 {
			return nil, errors.New("权限不足：你不是该组织成员，无法上传文件")
		}
	} else {
		// --- B. 个人库鉴权 ---
		// 必须是创建者本人
		if kb.CreatorID != userID {
			return nil, errors.New("权限不足：这不是你的个人知识库")
		}
	}

	// =================================================================
	// 📂 步骤 1: MinIO 上传
	// =================================================================
	src, err := fileHeader.Open()
	if err != nil {
		return nil, err
	}
	defer src.Close()

	storagePath, err := s.Data.UploadFile(ctx, src, fileHeader.Size, fileHeader.Filename)
	if err != nil {
		return nil, err
	}

	// =================================================================
	// 💾 步骤 2: 写入数据库
	// =================================================================
	fileConfig := map[string]interface{}{
		"storage_path": storagePath,
		"file_size":    fileHeader.Size,
		"file_ext":     strings.ToLower(filepath.Ext(fileHeader.Filename)),
	}
	configJSON, _ := json.Marshal(fileConfig)

	ds := &model.DataSource{
		KnowledgeBaseID: kbID, // 🔥 这里填入校验过的 kbID
		Type:            "file",
		Name:            fileHeader.Filename,
		Config:          datatypes.JSON(configJSON),
		Status:          "pending",
	}

	if err := s.Data.DB.WithContext(ctx).Create(ds).Error; err != nil {
		return nil, err
	}

	// =================================================================
	// ⚡ 步骤 3: 异步触发 ETL
	// =================================================================
	go func(dsID uint, path string, name string) {
		bgCtx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
		defer cancel()

		etlConfig := map[string]string{
			"storage_path": path,
			"file_name":    name,
		}
		etlBytes, _ := json.Marshal(etlConfig)

		s.updateDataSourceStatus(dsID, "parsing", "", 0, 0)

		resp, err := s.grpcClient.SyncDataSource(bgCtx, &pb.SyncRequest{
			KbId:         int64(kbID),
			DatasourceId: int64(dsID),
			Type:         "file",
			ConfigJson:   string(etlBytes),
		})

		if err != nil {
			log.Printf("❌ ETL 请求失败: %v", err)
			s.updateDataSourceStatus(dsID, "failed", err.Error(), 0, 0)
			return
		}
		if !resp.Success {
			log.Printf("❌ ETL 处理失败: %s", resp.ErrorMsg)
			s.updateDataSourceStatus(dsID, "failed", resp.ErrorMsg, 0, 0)
			return
		}

		log.Printf("✅ ETL 完成: %s (Chunks: %d)", name, resp.ChunksCount)
		s.updateDataSourceStatus(dsID, "active", "", int(resp.ChunksCount), int(resp.PageCount))

	}(ds.ID, storagePath, ds.Name)

	return ds, nil
}

// GetFile 获取文件流用于预览
func (s *RuntimeService) GetFile(ctx context.Context, fileName string) (*minio.Object, int64, error) {
	// 硬编码 bucket 名，生产环境建议从 conf 读取
	bucketName := "chimera-docs"
	return s.Data.GetFileStream(ctx, bucketName, fileName)
}

// 🔥 辅助方法：更新 DataSource 状态
func (s *RuntimeService) updateDataSourceStatus(id uint, status string, errMsg string, chunks int, pages int) {
	updates := map[string]interface{}{
		"status":         status,
		"error_msg":      errMsg,
		"last_sync_time": time.Now(),
	}
	if chunks > 0 {
		updates["chunk_count"] = chunks
	}
	if pages > 0 {
		updates["page_count"] = pages
	}
	s.Data.DB.Model(&model.DataSource{}).Where("id = ?", id).Updates(updates)
}
