package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"mime/multipart"
	"path/filepath"
	"strings"
	"time"
	"log"

	"Chimera/server/internal/core"
	"Chimera/server/internal/data"
	"Chimera/server/internal/dto"
	"Chimera/server/internal/model"

	"github.com/minio/minio-go/v7"
	"gorm.io/datatypes"
)

type DataSourceService struct {
	Data    *data.Data
	Adapter *RuntimeAdapter
}

func NewDataSourceService(data *data.Data, adapter *RuntimeAdapter) *DataSourceService {
	return &DataSourceService{
		Data:    data,
		Adapter: adapter,
	}
}

// CreateDataSource 通用创建接口 (API/SaaS源)
func (s *DataSourceService) CreateDataSource(ctx context.Context, userID uint, req dto.CreateDataSourceReq) (*model.DataSource, error) {
	// 1. 鉴权
	if err := s.checkKbPermission(req.KbID, userID); err != nil {
		return nil, err
	}

	// 2. 校验配置 (企业版注入点)
	if err := core.GlobalRegistry.Validate(req.Type, req.Config); err != nil {
		return nil, fmt.Errorf("配置校验失败: %v", err)
	}

	// 3. 序列化
	configBytes, err := json.Marshal(req.Config)
	if err != nil {
		return nil, errors.New("配置格式错误")
	}

	// 4. 落库
	ds := &model.DataSource{
		KnowledgeBaseID: req.KbID,
		Type:            req.Type,
		Name:            req.Name,
		Config:          datatypes.JSON(configBytes),
		Status:          "pending",
	}
	if err := s.Data.DB.WithContext(ctx).Create(ds).Error; err != nil {
		return nil, err
	}

	// 5. 触发 ETL
	s.triggerAsyncETL(ds.ID, req.KbID, req.Type, configBytes)

	return ds, nil
}

// UploadFile 上传文件接口 (文件源)
func (s *DataSourceService) UploadFile(ctx context.Context, fileHeader *multipart.FileHeader, userID uint, kbID uint) (*model.DataSource, error) {
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

	// 3. 构造配置
	configMap := map[string]interface{}{
		"storage_path": storagePath,
		"file_size":    fileHeader.Size,
		"file_ext":     strings.ToLower(filepath.Ext(fileHeader.Filename)),
		"file_name":    fileHeader.Filename,
	}
	configBytes, _ := json.Marshal(configMap)

	// 4. 落库
	ds := &model.DataSource{
		KnowledgeBaseID: kbID,
		Type:            "file",
		Name:            fileHeader.Filename,
		Config:          datatypes.JSON(configBytes),
		Status:          "pending",
	}
	if err := s.Data.DB.WithContext(ctx).Create(ds).Error; err != nil {
		return nil, err
	}

	// 5. 触发 ETL
	s.triggerAsyncETL(ds.ID, kbID, "file", configBytes)

	return ds, nil
}

// GetFile 获取文件流 (用于预览/下载)
func (s *DataSourceService) GetFile(ctx context.Context, fileName string) (*minio.Object, int64, error) {
	// 桶名硬编码或从配置读取
	bucketName := "chimera-docs"
	return s.Data.GetFileStream(ctx, bucketName, fileName)
}

// --- 私有辅助方法 ---

// checkKbPermission 鉴权
func (s *DataSourceService) checkKbPermission(kbID uint, userID uint) error {
	var kb model.KnowledgeBase
	if err := s.Data.DB.First(&kb, kbID).Error; err != nil {
		return errors.New("知识库不存在")
	}
	// 组织库鉴权
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
	// 个人库鉴权
	if kb.CreatorID != userID {
		return errors.New("权限不足")
	}
	return nil
}

// triggerAsyncETL 异步触发
func (s *DataSourceService) triggerAsyncETL(dsID uint, kbID uint, sourceType string, configBytes []byte) {
	go func() {
		// 1. 设置数据源状态为 "pending" 或 "queueing"
		s.updateDataSourceStatus(dsID, "queueing", "", 0, 0)

		// 2. 构造任务消息
		taskMap := map[string]interface{}{
			"task_id":       fmt.Sprintf("etl_%d_%d", dsID, time.Now().Unix()),
			"ds_id":         dsID,
			"kb_id":         kbID,
			"type":          sourceType,
			"config_json":   string(configBytes),
			"timestamp":     time.Now().Unix(),
		}
		payload, _ := json.Marshal(taskMap)

		// 3. 将任务推入 Redis 列表 (生产者)
		err := s.Data.PushTask(context.Background(), "chimera_etl_tasks", string(payload))
		if err != nil {
			s.updateDataSourceStatus(dsID, "failed", "任务入队失败: "+err.Error(), 0, 0)
			return
		}

		log.Printf("📦 [Go-Task] ETL Task pushed for DS:%d", dsID)
	}()
}

// updateDataSourceStatus 更新状态
func (s *DataSourceService) updateDataSourceStatus(id uint, status string, errMsg string, chunks, pages int) {
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
