package model

type User struct {
	BaseModel
	Username     string `gorm:"uniqueIndex;size:50;not null" json:"username"`
	PasswordHash string `gorm:"not null" json:"-"`
	Email        string `gorm:"size:100" json:"email"`
	Avatar       string `gorm:"size:255" json:"avatar"`

	// 系统级角色 (sys_admin, user) - 用于管理整个平台
	Role string `gorm:"default:'user'" json:"role"`

	// 🔥 我加入的组织 (通过中间表关联)
	Memberships []OrganizationMember `gorm:"foreignKey:UserID" json:"memberships"`
}
