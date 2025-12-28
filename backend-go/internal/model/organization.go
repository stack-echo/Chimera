package model

import "time"

type Organization struct {
	BaseModel
	Name        string `gorm:"size:100;not null" json:"name"`
	Description string `gorm:"size:255" json:"description"`
	Key         string `gorm:"uniqueIndex;size:50" json:"key"`

	OwnerID uint `gorm:"index;not null" json:"owner_id"`

	// 关联
	Members        []OrganizationMember `gorm:"foreignKey:OrganizationID" json:"members"`
	KnowledgeBases []KnowledgeBase      `gorm:"foreignKey:OrgID" json:"knowledge_bases"`
}

// OrganizationMember 中间表：记录用户在组织里的角色
type OrganizationMember struct {
	OrganizationID uint `gorm:"primaryKey" json:"organization_id"`
	UserID         uint `gorm:"primaryKey" json:"user_id"`

	// 角色: owner, admin, member
	Role     string    `gorm:"size:20;default:'member'" json:"role"`
	JoinedAt time.Time `json:"joined_at"`

	// 预加载关联
	User         User         `json:"user"`
	Organization Organization `json:"organization"`
}
