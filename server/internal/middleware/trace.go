package middleware

import (
	"context"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"strings"
)

// TraceContextKey 用于在 Context 中存储 Trace ID
const TraceContextKey = "traceID"

func TraceMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 1. 优先从 Header 获取（如果前端传了），否则生成新的
		traceID := c.GetHeader("X-Trace-Id")
		if traceID == "" {
			traceID = strings.ReplaceAll(uuid.New().String(), "-", "")
		}

		// 2. 存入 Gin Context
		c.Set(TraceContextKey, traceID)

		// 3. 存入标准 Context (GoLand/gRPC 常用)
		ctx := context.WithValue(c.Request.Context(), TraceContextKey, traceID)
		c.Request = c.Request.WithContext(ctx)

		// 4. 将 Trace ID 返回给前端 Header，方便调试
		c.Header("X-Trace-Id", traceID)

		c.Next()
	}
}