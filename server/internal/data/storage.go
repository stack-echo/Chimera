package data

import (
	"Chimera/server/internal/model"
	"context"
	"fmt"
	"io"
	"path/filepath"

	"github.com/google/uuid"
	"github.com/minio/minio-go/v7"
)

// ---------------------------------------------------------
// MinIO 相关操作 (Storage)
// ---------------------------------------------------------

// UploadFile 将文件流上传到 MinIO
// 返回: 存储路径(objectName), 错误
func (d *Data) UploadFile(ctx context.Context, file io.Reader, fileSize int64, originalFilename string) (string, error) {
	// 1. 生成安全的文件名 (UUID + 原始后缀)
	// 例如: "550e8400-e29b-41d4-a716-446655440000.pdf"
	ext := filepath.Ext(originalFilename)
	objectName := fmt.Sprintf("%s%s", uuid.New().String(), ext)

	// 桶名称建议从 Config 中读取，这里为演示先写死或作为参数
	bucketName := "chimera-docs"

	// 2. 执行上传
	_, err := d.Minio.PutObject(ctx, bucketName, objectName, file, fileSize, minio.PutObjectOptions{
		ContentType: "application/octet-stream", // 自动检测或由上层传入
	})
	if err != nil {
		return "", fmt.Errorf("minio put object error: %w", err)
	}

	// 返回存储路径 (bucket/objectName 或 纯 objectName，看需求)
	// 这里返回 objectName，方便后续拼接 URL
	return objectName, nil
}

// GetFileStream 从 MinIO 获取文件流
// 返回: 文件对象(需由调用者Close), 文件大小, 错误
func (d *Data) GetFileStream(ctx context.Context, bucketName string, objectName string) (*minio.Object, int64, error) {
	// 1. 获取对象流
	object, err := d.Minio.GetObject(ctx, bucketName, objectName, minio.GetObjectOptions{})
	if err != nil {
		return nil, 0, fmt.Errorf("minio get object error: %w", err)
	}

	// 2. 获取对象信息 (主要为了拿 Size)
	// Stat() 会检查对象是否存在，如果不存在这里会报错
	info, err := object.Stat()
	if err != nil {
		// 如果 Stat 失败，说明对象可能不存在或连接断开
		// 记得关闭 object，防止泄漏
		object.Close()
		return nil, 0, fmt.Errorf("minio stat object error: %w", err)
	}

	return object, info.Size, nil
}

// ---------------------------------------------------------
// Postgres 相关操作 (DB) - v0.2.0 新增
// ---------------------------------------------------------

// CreateDocument 在数据库创建文档记录
func (d *Data) CreateDocument(ctx context.Context, doc *model.DataSource) error {
	return d.DB.WithContext(ctx).Create(doc).Error
}
