package handler

import (
	"io"
	"net/http"
	"strings"

	"Chimera/server/internal/dto"
	"Chimera/server/internal/service"

	"github.com/gin-gonic/gin"
)

type ChatHandler struct {
	svc *service.ChatService
}

func NewChatHandler(svc *service.ChatService) *ChatHandler {
	return &ChatHandler{svc: svc}
}

// HandleChatSSE 处理对话接口 (兼容流式与非流式)
// POST /api/v1/chat/stream
func (h *ChatHandler) HandleChatSSE(c *gin.Context) {
	var req dto.ChatReq

	// 1. 绑定前端 JSON
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 2. 获取用户id
	userID, exists := c.Get("userID")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "未登录"})
		return
	}

	// 3. 创建通道用于接收 Service 的流式返回
	respChan := make(chan string)

	// 4. 异步调用 Service
	// 注意：传入 userID.(uint)
	go h.svc.StreamChat(c.Request.Context(), userID.(uint), req, respChan)

	// ==========================================
	// 分支 A: 非流式模式 (For Apifox 测试 / 第三方调用)
	// ==========================================
	if !req.Stream {
		var fullAnswer string
		// 循环读取通道
		for msg := range respChan {
			// 简单过滤掉 THINKING 标签，只返回内容 (或者你可以选择都返回)
			if !strings.HasPrefix(msg, "THOUGHT:") {
				fullAnswer += msg
			}
		}

		if strings.Contains(fullAnswer, "ERR: ⛔️") {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Access Denied",
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"answer": fullAnswer,
		})
		return
	}

	// ==========================================
	// 分支 B: 流式模式 (SSE, For Vue 前端)
	// ==========================================
	c.Writer.Header().Set("Content-Type", "text/event-stream")
	c.Writer.Header().Set("Cache-Control", "no-cache")
	c.Writer.Header().Set("Connection", "keep-alive")
	c.Writer.Header().Set("Transfer-Encoding", "chunked")

	c.Stream(func(w io.Writer) bool {
		if msg, ok := <-respChan; ok {
			// 直接透传给前端，前端去解析 "THOUGHT:" 前缀
			c.SSEvent("message", msg)
			return true
		}
		return false
	})
}
