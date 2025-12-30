package service

import (
	"Chimera/backend-go/internal/data"
	"Chimera/backend-go/internal/dto"
	"Chimera/backend-go/internal/model"
	"context"
	"fmt"
	"time"
)

type LogService struct {
	Data *data.Data
}

func NewLogService(data *data.Data) *LogService {
	return &LogService{Data: data}
}

// GetLogList 获取日志列表 (支持分页和筛选)
func (s *LogService) GetLogList(ctx context.Context, userID uint, req dto.LogListReq) (*dto.LogListResp, error) {
	var logs []model.AppRunLog
	var total int64

	db := s.Data.DB.Model(&model.AppRunLog{})

	// 1. 权限控制: 暂时只看自己所属组织的日志 (或者由上层 Handler 控制 OrgID)
	// 这里简化：查询用户有权限的 App (如果要做严格鉴权，需要关联 OrganizationMember)
	// 目前 v0.6.0 alpha 阶段，假设传入了 AppID，我们就不做太复杂的跨表鉴权了，先跑通数据。

	if req.AppID != "" {
		db = db.Where("app_id = ?", req.AppID)
	}
	if req.Status != "" {
		db = db.Where("status = ?", req.Status)
	}

	// 计算总数
	db.Count(&total)

	// 分页查询
	offset := (req.Page - 1) * req.PageSize
	// 预加载 User 信息？日志表里只存了 UserID
	// 这里用 Preload 需要在 Model 里定义关联，或者手动查。
	// 为了性能，列表页通常不查 User 详情，或者 Join 查询。
	if err := db.Order("created_at desc").Limit(req.PageSize).Offset(offset).Find(&logs).Error; err != nil {
		return nil, err
	}

	// 转换为 DTO
	var list []dto.LogSummary
	for _, l := range logs {
		// 截取 Query，防止列表页太长
		shortQuery := l.Query
		if len(shortQuery) > 50 {
			shortQuery = shortQuery[:50] + "..."
		}

		list = append(list, dto.LogSummary{
			ID:          l.ID,
			TraceID:     l.TraceID,
			AppID:       l.AppID,
			User:        fmt.Sprintf("User-%d", l.UserID), // 暂时显示 ID，后续优化
			Query:       shortQuery,
			Answer:      l.Answer,
			TotalTokens: l.TotalTokens,
			DurationMs:  l.DurationMs,
			Status:      l.Status,
			CreatedAt:   l.CreatedAt,
		})
	}

	return &dto.LogListResp{
		Total: total,
		List:  list,
	}, nil
}

// GetAppStats 获取应用统计数据 (图表用)
func (s *LogService) GetAppStats(ctx context.Context, req dto.AppStatsReq) (*dto.AppStatsResp, error) {
	// 1. 总体统计
	var totalStats struct {
		SumTokens   int64
		CountCalls  int64
		SumDuration int64
	}

	// 计算时间范围
	startTime := time.Now().AddDate(0, 0, -req.Days)

	db := s.Data.DB.Model(&model.AppRunLog{}).Where("created_at >= ?", startTime)
	if req.AppID != "" {
		db = db.Where("app_id = ?", req.AppID)
	}

	err := db.Select("sum(total_tokens) as sum_tokens, count(id) as count_calls, sum(duration_ms) as sum_duration").
		Scan(&totalStats).Error
	if err != nil {
		return nil, err
	}

	avgDuration := int64(0)
	if totalStats.CountCalls > 0 {
		avgDuration = totalStats.SumDuration / totalStats.CountCalls
	}

	// 2. 每日趋势 (聚合查询)
	// Postgres 使用 TO_CHAR(created_at, 'YYYY-MM-DD')
	type DailyRow struct {
		Date        string
		TotalTokens int64
		CallCount   int64
	}
	var dailyRows []DailyRow

	err = db.Select("TO_CHAR(created_at, 'YYYY-MM-DD') as date, sum(total_tokens) as total_tokens, count(id) as call_count").
		Group("date").
		Order("date").
		Scan(&dailyRows).Error
	if err != nil {
		return nil, err
	}

	// 转换
	var dailyMetrics []dto.DailyMetric
	for _, row := range dailyRows {
		dailyMetrics = append(dailyMetrics, dto.DailyMetric{
			Date:   row.Date,
			Tokens: row.TotalTokens,
			Calls:  row.CallCount,
		})
	}

	return &dto.AppStatsResp{
		TotalCalls:    totalStats.CountCalls,
		TotalTokens:   totalStats.SumTokens,
		AvgDurationMs: avgDuration,
		DailyStats:    dailyMetrics,
	}, nil
}
