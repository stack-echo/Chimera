package handler

import (
	"net/http"
	"strconv"

	"Chimera/backend-go/internal/service"
	"github.com/gin-gonic/gin"
)

type FileHandler struct {
	svc *service.RuntimeService
}

func NewFileHandler(svc *service.RuntimeService) *FileHandler {
	return &FileHandler{svc: svc}
}

// Upload 上传文件
// POST /api/v1/files/upload
// Form-Data: file=BINARY, kb_id=1
func (h *FileHandler) Upload(c *gin.Context) {
	// 1. 获取文件
	file, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "请上传文件"})
		return
	}

	// 2. 🔥 获取 kb_id (必填)
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

	// 3. 获取用户
	userID := c.GetUint("userID")

	// 4. 🔥 调用 Service (传入 kbID)
	ds, err := h.svc.UploadDocument(c.Request.Context(), file, userID, uint(kbID))
	if err != nil {
		// 区分一下是 400 (参数/权限) 还是 500 (MinIO/DB挂了)
		// 简单起见，统一报 500，或者你可以根据 error string 判断
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"code": 200,
		"data": gin.H{
			"id":     ds.ID,
			"name":   ds.Name,
			"status": ds.Status,
		},
	})
}
