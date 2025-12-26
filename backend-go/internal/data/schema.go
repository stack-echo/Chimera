package data

import (
	"gorm.io/gorm"
)

// ---------------------------------------------------------
// 1. 用户与权限 (RBAC)
// ---------------------------------------------------------

type User struct {
	gorm.Model
	Username     string `gorm:"uniqueIndex;size:50;not null" json:"username"`
	PasswordHash string `gorm:"not null" json:"-"` // 密码不返给前端
	Email        string `gorm:"size:100" json:"email"`
	Avatar       string `json:"avatar"`
	Role         string `gorm:"default:'user'" json:"role"` // admin, user

	// 组织隔离 (v0.2.0 预留)
	OrganizationID uint `gorm:"index" json:"organization_id"`
}

type Organization struct {
	gorm.Model
	Name string `gorm:"unique;size:100" json:"name"`
	Key  string `gorm:"uniqueIndex;size:50" json:"key"` // 用于 MinIO bucket 隔离
}

// ---------------------------------------------------------
// 2. 知识库管理 (文件夹树)
// ---------------------------------------------------------

type KnowledgeBase struct {
	gorm.Model
	Name        string `gorm:"size:100;not null" json:"name"`
	Description string `json:"description"`
	Type        string `gorm:"default:'folder'" json:"type"` // 'folder', 'repo'

	// 树状结构: ParentID 为空则是根目录
	ParentID *uint            `gorm:"index" json:"parent_id"`
	Children []*KnowledgeBase `gorm:"foreignKey:ParentID" json:"children,omitempty"`

	// 归属
	OwnerID  uint `gorm:"index;not null" json:"owner_id"`
	IsPublic bool `gorm:"default:false" json:"is_public"`
}

// ---------------------------------------------------------
// 3. 文档资产
// ---------------------------------------------------------

type Document struct {
	gorm.Model
	Title    string `gorm:"index" json:"title"`
	FileName string `json:"file_name"`
	FileSize int64  `json:"file_size"`
	FileType string `json:"file_type"` // .pdf, .docx

	// 存储路径: minio://bucket/org_id/kb_id/uuid.pdf
	StoragePath string `gorm:"not null" json:"storage_path"`

	// 关联
	KnowledgeBaseID uint `gorm:"index;not null" json:"knowledge_base_id"`

	// 状态机: pending -> parsing -> embedding -> success / failed
	Status   string `gorm:"default:'pending';index" json:"status"`
	ErrorMsg string `json:"error_msg"`

	// 版本控制: 记录用什么解析出来的
	ParserType string `gorm:"default:'docling'" json:"parser_type"`
	ChunkCount int    `json:"chunk_count"`
}
