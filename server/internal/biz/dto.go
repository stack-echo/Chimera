package biz

// ChatRequest 是前端发来的 JSON
type ChatRequest struct {
	Query     string `json:"query" binding:"required"`
	SessionID string `json:"session_id"`
	UseGraph  bool   `json:"use_graph"`
	UseSearch bool   `json:"use_search"`
}

// 这里的结构体只用于绑定请求，响应我们直接写流，不需要定义结构体
