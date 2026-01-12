package model

import (
	"gorm.io/datatypes"
	"time"
)

type DataSource struct {
	BaseModel
	KnowledgeBaseID uint `gorm:"index;not null" json:"knowledge_base_id"`

	// 类型区分: "file", "feishu_wiki", "dingtalk", "web_crawl"
	Type string `gorm:"size:50;not null;index" json:"type"`

	// 名称: 文件名 或 飞书知识库标题
	Name string `gorm:"size:255;not null" json:"name"`

	// 🔥 核心配置 (JSON) - 所有的源数据都存在这
	// File:   {"storage_path": "minio://...", "size": 1024, "ext": ".pdf"}
	// Feishu: {"app_id": "...", "root_token": "..."}
	Config datatypes.JSON `json:"config"`

	// 状态机: pending -> syncing -> active / error
	Status   string `gorm:"default:'pending';index" json:"status"`
	ErrorMsg string `json:"error_msg"`

	// 统计数据
	ChunkCount     int       `json:"chunk_count"`
	PageCount      int       `json:"page_count"`
	LastSyncTime   time.Time `json:"last_sync_time"`
	KnowledgeCount int     `json:"knowledge_count"`    // 总实体数
	LinkageRate    float64 `json:"linkage_rate"`       // 实体对齐率 (0-1)
	VisualWeight   float64 `json:"visual_weight"`      // 视觉知识占比
}
