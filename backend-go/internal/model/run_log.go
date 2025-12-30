package model

import (
	"time"

	"gorm.io/datatypes"
)

// AppRunLog 记录每一次智能体运行的详细信息
type AppRunLog struct {
	ID        uint      `gorm:"primarykey" json:"id"`
	CreatedAt time.Time `json:"created_at"`

	// 索引字段 (用于多租户查询)
	OrgID     uint   `gorm:"index;not null" json:"org_id"`
	AppID     string `gorm:"index;not null" json:"app_id"`
	UserID    uint   `gorm:"index;not null" json:"user_id"`
	SessionID string `gorm:"index" json:"session_id"`
	TraceID   string `gorm:"index" json:"trace_id"` // 关联 SigNoz

	// 输入输出快照
	Query  string `gorm:"type:text" json:"query"`
	Answer string `gorm:"type:text" json:"answer"` // 最终完整回答

	// 统计指标
	TotalTokens      int   `json:"total_tokens"`
	PromptTokens     int   `json:"prompt_tokens"`
	CompletionTokens int   `json:"completion_tokens"`
	DurationMs       int64 `json:"duration_ms"`

	Status string `gorm:"size:20" json:"status"` // success, failed

	// 扩展字段 (留给未来存详细步骤 JSON)
	MetaInfo datatypes.JSON `json:"meta_info"`
}
