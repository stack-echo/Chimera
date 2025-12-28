package dto

import "time"

// CreateOrgReq 创建组织请求参数
type CreateOrgReq struct {
	Name        string `json:"name" binding:"required"`
	Description string `json:"description"`
	// 👇 改为 omitempty，允许不传
	Key string `json:"key" binding:"omitempty,alphanum,min=3,max=20"`
}

// OrgResp 组织响应数据
type OrgResp struct {
	ID          uint      `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	Key         string    `json:"key"`
	OwnerID     uint      `json:"owner_id"`
	CreatedAt   time.Time `json:"created_at"`
}
