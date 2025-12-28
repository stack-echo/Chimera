package dto

import "time"

type CreateKBReq struct {
	Name        string `json:"name" binding:"required"`
	Description string `json:"description"`
	Type        string `json:"type" binding:"oneof=folder repo"` // 暂时只用 folder

	// 🔥 核心字段：如果不传(0/null)，则是个人知识库
	OrgID uint `json:"org_id"`
}

type KBResp struct {
	ID          uint      `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	Type        string    `json:"type"`
	CreatorID   uint      `json:"creator_id"`
	OrgID       *uint     `json:"org_id"` // 指针类型，返回 null 表示个人
	CreatedAt   time.Time `json:"created_at"`
}
