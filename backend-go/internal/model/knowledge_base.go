package model

type KnowledgeBase struct {
	BaseModel
	Name        string `gorm:"size:100;not null" json:"name"`
	Description string `json:"description"`
	Type        string `gorm:"default:'folder'" json:"type"` // folder, repo

	// 树状结构
	ParentID *uint            `gorm:"index" json:"parent_id"`
	Children []*KnowledgeBase `gorm:"foreignKey:ParentID" json:"children,omitempty"`

	// --- 核心改动：双重归属 ---
	CreatorID uint  `gorm:"index;not null" json:"creator_id"` // 谁创建的
	OrgID     *uint `gorm:"index;default:null" json:"org_id"` // 属于哪个组织 (NULL=个人)

	IsPublic bool `gorm:"default:false" json:"is_public"`

	// 关联文档
	Documents []Document `json:"documents"`
}
