package handler

import (
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"

	"Chimera/backend-go/internal/dto"
	"Chimera/backend-go/internal/service"

	"github.com/gin-gonic/gin"
)

type ChatHandler struct {
	svc *service.RuntimeService
}

func NewChatHandler(svc *service.RuntimeService) *ChatHandler {
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

// HandleUpload 修改版：适配 DataSource 和 KB_ID
func (h *ChatHandler) HandleUpload(c *gin.Context) {
	// 1. 获取用户 ID
	userID := c.GetUint("userID")

	// 2. 获取文件
	fileHeader, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "文件无效"})
		return
	}

	// 3. 🔥 获取 kb_id (新增必填项)
	kbIDStr := c.PostForm("kb_id")
	if kbIDStr == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "缺少 kb_id 参数"})
		return
	}
	kbID, err := strconv.Atoi(kbIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "kb_id 格式错误"})
		return
	}

	// 4. 调用 Service (传入 kbID)
	// 返回值现在是 *model.DataSource
	dataSource, err := h.svc.UploadDocument(c.Request.Context(), fileHeader, userID, uint(kbID))
	if err != nil {
		// 简单区分一下错误类型
		statusCode := http.StatusInternalServerError
		if strings.Contains(err.Error(), "权限不足") || strings.Contains(err.Error(), "不存在") {
			statusCode = http.StatusForbidden
		}
		c.JSON(statusCode, gin.H{"error": err.Error()})
		return
	}

	// 5. 返回结果 (适配 DataSource 字段)
	c.JSON(http.StatusOK, gin.H{
		"msg": "上传成功",
		"data": gin.H{
			"id":     dataSource.ID,
			"name":   dataSource.Name,   // 文件名
			"status": dataSource.Status, // pending / parsing
			"type":   dataSource.Type,   // file
		},
	})
}

// HandleGetFile 下载/预览文件
func (h *ChatHandler) HandleGetFile(c *gin.Context) {
	filename := c.Param("filename")

	obj, size, err := h.svc.GetFile(c.Request.Context(), filename)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "文件获取失败: " + err.Error()})
		return
	}
	defer obj.Close()

	c.Header("Content-Description", "File Transfer")
	c.Header("Content-Transfer-Encoding", "binary")
	c.Header("Content-Disposition", "inline; filename="+filename)
	c.Header("Content-Type", "application/pdf") // 假设都是 PDF，生产环境应根据后缀判断
	c.Header("Content-Length", fmt.Sprintf("%d", size))

	_, err = io.Copy(c.Writer, obj)
	if err != nil {
		fmt.Printf("Stream file error: %v\n", err)
	}
}
