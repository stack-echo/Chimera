package dto

// ChatReq 定义前端发送的聊天请求参数
type ChatReq struct {
	Query     string `json:"query" binding:"required"` // 用户的问题
	SessionID string `json:"session_id"`               // 会话ID (可选)

	// 🔥 v0.4.0 新增字段：用于指定搜索范围
	KbID  uint `json:"kb_id"`  // 指定知识库 ID (0 表示不指定)
	OrgID uint `json:"org_id"` // 指定组织 ID (0 表示不指定)

	// 默认为 false。前端 Vue 需要传 true，Apifox 测试传 false (或不传)
	Stream bool `json:"stream"`

	// 如果需要支持历史记录，可以在这里加
	// History []Message `json:"history"`
}
