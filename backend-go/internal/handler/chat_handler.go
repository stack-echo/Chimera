package handler

import (
	"Chimera-RAG/backend-go/internal/dto"
	"Chimera-RAG/backend-go/internal/service"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

type ChatHandler struct {
	svc *service.RagService
}

func NewChatHandler(svc *service.RagService) *ChatHandler {
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
	// (放在这里是因为不管流不流，Service 都需要这个通道)
	respChan := make(chan string)

	// 4. 异步调用 Service (生产数据)
	// 注意：请确保 h.svc.StreamChat 内部在发完消息后会 close(respChan)，否则下面会死锁
	// 传入 userID.(uint)
	go h.svc.StreamChat(c.Request.Context(), userID.(uint), req, respChan)

	// ==========================================
	// 分支 A: 非流式模式 (For Apifox 测试 / 第三方调用)
	// ==========================================
	if !req.Stream {
		var fullAnswer string
		// 循环读取通道，直到 Service 关闭通道
		for msg := range respChan {
			fullAnswer += msg
		}
		
		if strings.Contains(fullAnswer, "ERR: ⛔️") {
			// 如果检测到这个特定的错误标记，返回 403 Forbidden
			c.JSON(http.StatusForbidden, gin.H{
				"error":   "Access Denied: You do not have permission to access this Knowledge Base.",
				"details": fullAnswer,
			})
			return
		}

		// 拼接完成后，一次性返回 JSON
		c.JSON(http.StatusOK, gin.H{
			"answer":  fullAnswer,
			"sources": []string{}, // 如果你的 channel 还没传 sources，暂时留空
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
			c.SSEvent("message", msg)
			return true
		}
		return false
	})
}

// HandleUpload 修改版
func (h *ChatHandler) HandleUpload(c *gin.Context) {
	// 1. 获取用户 ID
	userID := c.GetUint("userID") // 假设中间件设置了 uint 类型的 userID

	// 2. 获取文件
	fileHeader, err := c.FormFile("file")
	if err != nil {
		c.JSON(400, gin.H{"error": "文件无效"})
		return
	}

	// 3. 调用 Service
	doc, err := h.svc.UploadDocument(c.Request.Context(), fileHeader, userID)
	if err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		return
	}

	// 4. 返回结果
	c.JSON(200, gin.H{
		"msg":    "上传成功",
		"doc_id": doc.ID,
		"path":   doc.StoragePath,
	})
}

// HandleGetFile 下载/预览文件
// GET /api/v1/file/:filename
func (h *ChatHandler) HandleGetFile(c *gin.Context) {
	filename := c.Param("filename")

	// 1. 调用 Service 层获取流
	// 注意：obj 是一个 ReadCloser，必须关闭
	obj, size, err := h.svc.GetFile(c.Request.Context(), filename)
	if err != nil {
		// 生产环境建议区分 "文件不存在" 和 "服务器错误"
		c.JSON(http.StatusNotFound, gin.H{"error": "文件获取失败: " + err.Error()})
		return
	}
	// 🔥 重要：流传输完成后关闭连接
	defer obj.Close()

	// 2. 设置 HTTP 响应头
	// 告诉浏览器这是一个 PDF，文件大小是多少（方便显示进度条）
	c.Header("Content-Description", "File Transfer")
	c.Header("Content-Transfer-Encoding", "binary")
	c.Header("Content-Disposition", "inline; filename="+filename) // inline=浏览器内预览, attachment=强制下载
	c.Header("Content-Type", "application/pdf")
	c.Header("Content-Length", fmt.Sprintf("%d", size))

	// 3. 将流拷贝到响应体 (Stream)
	// 这一步会阻塞直到文件传输完成，内存占用极低
	_, err = io.Copy(c.Writer, obj)
	if err != nil {
		// 如果传输过程中断，通常也没法写 JSON 错误了，只能记录日志
		fmt.Printf("Stream file error: %v\n", err)
	}
}
