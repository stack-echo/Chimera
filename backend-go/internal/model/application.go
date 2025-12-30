package model

import (
	"gorm.io/datatypes" // 需要 go get gorm.io/datatypes
)

type Application struct {
	BaseModel
	Name        string `gorm:"size:100;not null" json:"name"`
	Description string `gorm:"size:255" json:"description"`
	Avatar      string `json:"avatar"`

	// 归属
	OrgID     *uint `gorm:"index" json:"org_id"`
	CreatorID uint  `gorm:"index;not null" json:"creator_id"`

	// 🤖 智能体配置 (JSON)
	// 包含: {"model": "deepseek-v3", "prompt": "你是一个...", "temperature": 0.7}
	AgentConfig datatypes.JSON `json:"agent_config"`

	// 🔗 关联知识库 (多对多)
	// GORM 会自动创建 application_knowledge_bases 中间表
	KnowledgeBases []*KnowledgeBase `gorm:"many2many:app_kb_relations;" json:"knowledge_bases"`

	Status string `gorm:"default:'active'" json:"status"` // active, disabled
}
