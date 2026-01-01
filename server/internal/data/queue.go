package data

import (
	"context"
	"fmt"
)

// ---------------------------------------------------------
// Redis 相关操作 (Queue)
// ---------------------------------------------------------

// PushTask 将任务推送到 Redis 队列
func (d *Data) PushTask(ctx context.Context, queueName string, payload string) error {
	// 使用 RPush (右进) 配合 Worker 的 BLPop (左出) 实现 FIFO 队列
	err := d.Redis.RPush(ctx, queueName, payload).Err()
	if err != nil {
		return fmt.Errorf("redis push error: %w", err)
	}
	return nil
}
