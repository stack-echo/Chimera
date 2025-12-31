package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"mime/multipart"
	"path/filepath"
	"strings"
	"time"

	pb "Chimera/backend-go/api/runtime/v1"
	"Chimera/backend-go/internal/data"
	"Chimera/backend-go/internal/dto"
	"Chimera/backend-go/internal/model"

	"github.com/minio/minio-go/v7"
	"gorm.io/datatypes"
)

// RuntimeService 核心业务逻辑层
type RuntimeService struct {
	grpcClient pb.RuntimeServiceClient
	Data       *data.Data
}

func NewRuntimeService(client pb.RuntimeServiceClient, data *data.Data) *RuntimeService {
	return &RuntimeService{
		grpcClient: client,
		Data:       data,
	}
}

// =================================================================================
// 1. 核心运行接口 (Chat / Workflow)
// =================================================================================

// StreamChat 处理对话请求
func (s *RuntimeService) StreamChat(ctx context.Context, userID uint, req dto.ChatReq, respChan chan<- string) {
	defer close(respChan)

	// 1. 安全检查
	if req.KbID > 0 {
		if err := s.checkKbPermission(req.KbID, userID); err != nil {
			log.Printf("🚨 StreamChat 鉴权失败: %v", err)
			// 返回特殊错误标识供 Handler 处理状态码
			respChan <- fmt.Sprintf("ERR: ⛔️ %s", err.Error())
			return
		}
	}

	// 2. 构造配置
	// OrgID 逻辑：如果 KB 属于组织，则以 KB 的 OrgID 为准；否则看请求
	// 这里简化处理，直接传 req 的参数，Python 端会根据 kb_ids 去查 Qdrant payload
	configData := map[string]interface{}{
		"kb_ids": []uint{req.KbID},
		"org_id": req.OrgID,
	}
	configBytes, _ := json.Marshal(configData)

	// 3. 构造 gRPC 请求
	grpcReq := &pb.RunAgentRequest{
		AppId:         "default_chat_app", // v0.6.0 将从 req.AppID 获取
		Query:         req.Query,
		SessionId:     req.SessionID,
		AppConfigJson: string(configBytes),
	}

	// 4. 调用 Python Runtime
	stream, err := s.grpcClient.RunAgent(ctx, grpcReq)
	if err != nil {
		log.Printf("❌ gRPC 调用失败: %v", err)
		respChan <- "ERR: 服务端连接失败"
		return
	}

	// 5. 转发流式响应
	var fullAnswerBuilder strings.Builder

	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			log.Printf("❌ gRPC 流中断: %v", err)
			return
		}

		switch resp.Type {
		case "delta":
			respChan <- resp.Payload
			fullAnswerBuilder.WriteString(resp.Payload)
		case "thought":
			respChan <- "THOUGHT: " + resp.Payload
		case "reference":
			respChan <- "REF: " + resp.Payload
		case "summary":
			log.Printf("📊 执行报告: Tokens=%d, Time=%dms", resp.Summary.TotalTokens, resp.Summary.TotalDurationMs)
			// 异步落库
			go s.saveRunLog(userID, req, resp.Summary, fullAnswerBuilder.String())
		case "error":
			log.Printf("❌ Agent Error: %s", resp.Payload)
			respChan <- fmt.Sprintf("\n[系统错误]: %s", resp.Payload)
		}
	}
}

// =================================================================================
// 2. 数据源管理接口 (File / Feishu / ETL)
// =================================================================================

// UploadDocument 上传文件并创建数据源
func (s *RuntimeService) UploadDocument(ctx context.Context, fileHeader *multipart.FileHeader, userID uint, kbID uint) (*model.DataSource, error) {
	// 1. 鉴权
	if err := s.checkKbPermission(kbID, userID); err != nil {
		return nil, err
	}

	// 2. MinIO 上传
	src, err := fileHeader.Open()
	if err != nil {
		return nil, err
	}
	defer src.Close()

	storagePath, err := s.Data.UploadFile(ctx, src, fileHeader.Size, fileHeader.Filename)
	if err != nil {
		return nil, err
	}

	// 3. 构造 Config JSON
	configMap := map[string]interface{}{
		"storage_path": storagePath,
		"file_size":    fileHeader.Size,
		"file_ext":     strings.ToLower(filepath.Ext(fileHeader.Filename)),
		"file_name":    fileHeader.Filename, // Python端 FileConnector 需要这个
	}
	configJSON, _ := json.Marshal(configMap)

	// 4. 数据库落库
	ds := &model.DataSource{
		KnowledgeBaseID: kbID,
		Type:            "file",
		Name:            fileHeader.Filename,
		Config:          datatypes.JSON(configJSON),
		Status:          "pending",
	}
	if err := s.Data.DB.WithContext(ctx).Create(ds).Error; err != nil {
		return nil, err
	}

	// 5. 触发异步 ETL (复用逻辑)
	s.triggerAsyncETL(ds.ID, kbID, "file", configJSON)

	return ds, nil
}

// CreateFeishuSource 创建飞书数据源
func (s *RuntimeService) CreateFeishuSource(ctx context.Context, userID uint, req dto.CreateDataSourceReq) (*model.DataSource, error) {
	// 1. 鉴权
	if err := s.checkKbPermission(req.KbID, userID); err != nil {
		return nil, err
	}

	// 2. 构造 Config JSON
	configMap := map[string]string{
		"app_id":        req.FeishuConfig.AppID,
		"app_secret":    req.FeishuConfig.AppSecret,
		"wiki_space_id": req.FeishuConfig.WikiSpaceID,
	}
	configJSON, _ := json.Marshal(configMap)

	// 3. 数据库落库
	ds := &model.DataSource{
		KnowledgeBaseID: req.KbID,
		Type:            "feishu", // 对应 Python 端的工厂 key
		Name:            req.Name,
		Config:          datatypes.JSON(configJSON),
		Status:          "pending",
	}
	if err := s.Data.DB.WithContext(ctx).Create(ds).Error; err != nil {
		return nil, err
	}

	// 4. 触发异步 ETL
	s.triggerAsyncETL(ds.ID, req.KbID, "feishu", configJSON)

	return ds, nil
}

// GetFile 下载文件流
func (s *RuntimeService) GetFile(ctx context.Context, fileName string) (*minio.Object, int64, error) {
	bucketName := "chimera-docs"
	return s.Data.GetFileStream(ctx, bucketName, fileName)
}

// =================================================================================
// 3. 私有辅助方法 (Helpers)
// =================================================================================

// checkKbPermission 统一鉴权逻辑
func (s *RuntimeService) checkKbPermission(kbID uint, userID uint) error {
	var kb model.KnowledgeBase
	if err := s.Data.DB.First(&kb, kbID).Error; err != nil {
		return errors.New("知识库不存在")
	}

	// 组织库
	if kb.OrgID != nil {
		var count int64
		s.Data.DB.Model(&model.OrganizationMember{}).
			Where("organization_id = ? AND user_id = ?", *kb.OrgID, userID).
			Count(&count)
		if count == 0 {
			return errors.New("权限不足：你不是该组织成员")
		}
		return nil
	}

	// 个人库
	if kb.CreatorID != userID {
		return errors.New("权限不足：这不是你的个人知识库")
	}
	return nil
}

// triggerAsyncETL 统一触发 Python ETL
func (s *RuntimeService) triggerAsyncETL(dsID uint, kbID uint, sourceType string, configBytes []byte) {
	go func() {
		// 30分钟超时，适应大文件或大量飞书文档同步
		bgCtx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
		defer cancel()

		s.updateDataSourceStatus(dsID, "syncing", "", 0, 0)
		log.Printf("🚀 [ETL Start] SourceID=%d Type=%s", dsID, sourceType)

		// 调用 gRPC
		resp, err := s.grpcClient.SyncDataSource(bgCtx, &pb.SyncRequest{
			KbId:         int64(kbID),
			DatasourceId: int64(dsID),
			Type:         sourceType,
			ConfigJson:   string(configBytes),
		})

		// 错误处理
		if err != nil {
			log.Printf("❌ [ETL Error] RPC Failed: %v", err)
			s.updateDataSourceStatus(dsID, "failed", fmt.Sprintf("RPC Error: %v", err), 0, 0)
			return
		}

		if !resp.Success {
			log.Printf("❌ [ETL Error] Python Logic Failed: %s", resp.ErrorMsg)
			s.updateDataSourceStatus(dsID, "failed", resp.ErrorMsg, 0, 0)
			return
		}

		// 成功
		log.Printf("✅ [ETL Success] SourceID=%d Chunks=%d Pages=%d", dsID, resp.ChunksCount, resp.PageCount)
		s.updateDataSourceStatus(dsID, "active", "", int(resp.ChunksCount), int(resp.PageCount))
	}()
}

// updateDataSourceStatus 更新数据库状态
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
	if err := s.Data.DB.Model(&model.DataSource{}).Where("id = ?", id).Updates(updates).Error; err != nil {
		log.Printf("❌ DB Update Failed: %v", err)
	}
}

// saveRunLog 保存监控日志
func (s *RuntimeService) saveRunLog(userID uint, req dto.ChatReq, summary *pb.RunSummary, answer string) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	runLog := &model.AppRunLog{
		OrgID:            req.OrgID,
		AppID:            "default_chat_app",
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