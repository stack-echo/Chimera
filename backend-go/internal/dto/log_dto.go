package dto

import "time"

// LogListReq 查询日志列表请求
type LogListReq struct {
	Page     int    `form:"page,default=1"`
	PageSize int    `form:"page_size,default=20"`
	AppID    string `form:"app_id"` // 选填，筛选特定应用
	Status   string `form:"status"` // success, failed
}

// LogListResp 日志列表响应
type LogListResp struct {
	Total int64        `json:"total"`
	List  []LogSummary `json:"list"`
}

type LogSummary struct {
	ID          uint      `json:"id"`
	TraceID     string    `json:"trace_id"`
	AppID       string    `json:"app_id"`
	User        string    `json:"user"` // 用户名
	Query       string    `json:"query"`
	Answer      string    `json:"answer"`
	TotalTokens int       `json:"total_tokens"`
	DurationMs  int64     `json:"duration_ms"`
	Status      string    `json:"status"`
	CreatedAt   time.Time `json:"created_at"`
}

// AppStatsReq 统计请求
type AppStatsReq struct {
	AppID string `form:"app_id"`
	Days  int    `form:"days,default=7"` // 最近几天
}

// AppStatsResp 统计响应
type AppStatsResp struct {
	TotalCalls    int64         `json:"total_calls"`
	TotalTokens   int64         `json:"total_tokens"`
	AvgDurationMs int64         `json:"avg_duration_ms"`
	DailyStats    []DailyMetric `json:"daily_stats"`
}

type DailyMetric struct {
	Date   string `json:"date"`
	Tokens int64  `json:"tokens"`
	Calls  int64  `json:"calls"`
}
