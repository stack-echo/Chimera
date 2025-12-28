package handler

import (
	"net/http"
	"strconv"

	"Chimera-RAG/backend-go/internal/service"
	"github.com/gin-gonic/gin"
)

type FileHandler struct {
	svc *service.FileService
}

func NewFileHandler(svc *service.FileService) *FileHandler {
	return &FileHandler{svc: svc}
}

// Upload 上传文件
// POST /api/v1/files/upload
// Form-Data: file=BINARY, kb_id=1
func (h *FileHandler) Upload(c *gin.Context) {
	// 1. 获取文件
	file, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "请上传文件 (key='file')"})
		return
	}

	// 2. 获取 kb_id
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

	// 3. 获取 UserID
	userID, exists := c.Get("userID")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "未登录"})
		return
	}

	// 4. 调用 Service
	resp, err := h.svc.UploadFile(c.Request.Context(), userID.(uint), file, uint(kbID))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"data": resp})
}
