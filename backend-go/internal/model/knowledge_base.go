package model

type KnowledgeBase struct {
	BaseModel
	Name        string `gorm:"size:100;not null" json:"name"`
	Description string `json:"description"`
	Avatar      string `json:"avatar"`

	// 归属
	OrgID     *uint `gorm:"index" json:"org_id"`
	CreatorID uint  `gorm:"index;not null" json:"creator_id"`

	// 🔗 关联数据源 (一对多)
	DataSources []DataSource `gorm:"foreignKey:KnowledgeBaseID" json:"data_sources"`
}
