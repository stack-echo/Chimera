package dto

// CreateDataSourceReq 创建数据源请求
type CreateDataSourceReq struct {
	KbID uint   `json:"kb_id" binding:"required"`
	Type string `json:"type" binding:"required"`
	Name string `json:"name" binding:"required"`

	// 前端传来的 { "app_id": "...", "secret": "..." } 会被自动解析进这个 map
	Config map[string]interface{} `json:"config"`
}
