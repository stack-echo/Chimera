package service

import (
	"context"
	"errors"
	"fmt"
	"mime/multipart"
	"path/filepath"
	"time"

	"Chimera-RAG/backend-go/internal/data"
	"Chimera-RAG/backend-go/internal/dto"
	"Chimera-RAG/backend-go/internal/model"
	"github.com/google/uuid"
	"github.com/minio/minio-go/v7"

	pb "Chimera-RAG/backend-go/api/rag/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type FileService struct {
	Data *data.Data
}

func NewFileService(data *data.Data) *FileService {
	return &FileService{Data: data}
}

// UploadFile 上传文件并绑定到知识库
func (s *FileService) UploadFile(ctx context.Context, userID uint, fileHeader *multipart.FileHeader, kbID uint) (*dto.FileResp, error) {
	// 1. 查找知识库信息 (用于鉴权)
	var kb model.KnowledgeBase
	if err := s.Data.DB.First(&kb, kbID).Error; err != nil {
		return nil, errors.New("知识库不存在")
	}

	// 2. 级联鉴权
	if kb.OrgID != nil {
		// --- 组织库鉴权 ---
		var count int64
		s.Data.DB.Model(&model.OrganizationMember{}).
			Where("organization_id = ? AND user_id = ?", *kb.OrgID, userID).
			Count(&count)
		if count == 0 {
			return nil, errors.New("权限不足：你不是该组织成员，无法上传文件")
		}
	} else {
		// --- 个人库鉴权 ---
		if kb.CreatorID != userID {
			return nil, errors.New("权限不足：这不是你的个人知识库")
		}
	}

	// 3. 打开文件流
	src, err := fileHeader.Open()
	if err != nil {
		return nil, err
	}
	defer src.Close()

	// 4. 生成存储路径 (建议: org_id/kb_id/uuid.pdf 或 user_id/kb_id/uuid.pdf)
	// 这里为了简单，统一用: kbs/{kb_id}/{uuid}{ext}
	ext := filepath.Ext(fileHeader.Filename)
	newFileName := uuid.New().String() + ext
	objectName := fmt.Sprintf("kbs/%d/%s", kb.ID, newFileName)
	bucketName := "chimera-docs" // 应该从配置读取，这里先硬编码或从 cfg 传进来

	// 5. 上传到 MinIO
	_, err = s.Data.Minio.PutObject(ctx, bucketName, objectName, src, fileHeader.Size, minio.PutObjectOptions{
		ContentType: fileHeader.Header.Get("Content-Type"),
	})
	if err != nil {
		return nil, fmt.Errorf("MinIO 上传失败: %v", err)
	}

	// 6. 数据库落库
	doc := &model.Document{
		Title:           fileHeader.Filename, // 默认标题为文件名
		FileName:        fileHeader.Filename,
		FileSize:        fileHeader.Size,
		FileType:        ext,
		StoragePath:     objectName, // minio://chimera-docs/kbs/1/xyz.pdf
		KnowledgeBaseID: kb.ID,
		OwnerID:         userID,    // 谁上传的
		Status:          "pending", // 待解析
	}

	if err := s.Data.DB.Create(doc).Error; err != nil {
		return nil, errors.New("文件元数据保存失败")
	}

	// ---------------------------------------------------------
	// 🔥 7. 异步触发 Python 解析 (Fire and Forget)
	// ---------------------------------------------------------
	go func(docID uint, storagePath string, fileName string) {
		// 创建一个新的背景上下文 (因为外层的 ctx 请求结束就会取消)
		bgCtx := context.Background()

		// 建立 gRPC 连接 (也可以在 Data 层维护一个长连接池，这里先简单短连接)
		// 注意：地址应该从 conf 读取，这里暂时硬编码 "localhost:50051"
		conn, err := grpc.Dial("localhost:50051", grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			fmt.Printf("❌ gRPC 连接失败: %v\n", err)
			s.updateDocStatus(docID, "failed", err.Error(), 0, 0)
			return
		}
		defer conn.Close()

		client := pb.NewRagServiceClient(conn)

		// 修改数据库状态为 parsing
		s.updateDocStatus(docID, "parsing", "", 0, 0)

		// 发送请求
		resp, err := client.ParseAndIngest(bgCtx, &pb.ParseRequest{
			StoragePath: storagePath,
			FileName:    fileName,
			DocId:       int64(docID),
			KbId:        int64(kbID),
		})

		if err != nil {
			fmt.Printf("❌ Python 解析出错: %v\n", err)
			s.updateDocStatus(docID, "failed", err.Error(), 0, 0)
			return
		}

		if !resp.Success {
			s.updateDocStatus(docID, "failed", resp.ErrorMsg, 0, 0)
			return
		}

		// 成功！
		s.updateDocStatus(docID, "success", "", int(resp.ChunkCount), int(resp.PageCount))
		fmt.Printf("✅ 文档解析成功: %s (Chunks: %d)\n", fileName, resp.ChunkCount)

	}(doc.ID, doc.StoragePath, doc.FileName) // 传入参数

	return &dto.FileResp{
		ID:        doc.ID,
		Title:     doc.Title,
		FileName:  doc.FileName,
		Size:      doc.FileSize,
		Status:    doc.Status,
		CreatedAt: doc.CreatedAt.Format(time.RFC3339),
	}, nil
}

// 辅助方法：更新数据库状态
func (s *FileService) updateDocStatus(id uint, status string, errMsg string, chunks int, pages int) {
	updates := map[string]interface{}{
		"status":    status,
		"error_msg": errMsg,
	}
	if chunks > 0 {
		updates["chunk_count"] = chunks
	}
	if pages > 0 {
		updates["page_count"] = pages
	}
	s.Data.DB.Model(&model.Document{}).Where("id = ?", id).Updates(updates)
}
