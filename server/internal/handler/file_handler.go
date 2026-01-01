package handler

import (
	"fmt"
	"io"
	"net/http"
	"strconv"

	"Chimera/server/internal/service"
	"github.com/gin-gonic/gin"
)

type FileHandler struct {
	// 🔥 关键修改：依赖 DataSourceService
	svc *service.DataSourceService
}

func NewFileHandler(svc *service.DataSourceService) *FileHandler {
	return &FileHandler{svc: svc}
}

// Upload 上传
func (h *FileHandler) Upload(c *gin.Context) {
	file, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "请上传文件"})
		return
	}

	kbIDStr := c.PostForm("kb_id")
	if kbIDStr == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "缺少 kb_id"})
		return
	}
	kbID, _ := strconv.Atoi(kbIDStr)
	userID := c.GetUint("userID")

	// 调用 DataSourceService 的 UploadFile
	ds, err := h.svc.UploadFile(c.Request.Context(), file, userID, uint(kbID))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"code": 200, "data": ds})
}

func (h *FileHandler) HandleGetFile(c *gin.Context) {
	filename := c.Param("filename")

	// 调用 dsSvc 的 GetFile
	obj, size, err := h.svc.GetFile(c.Request.Context(), filename)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "文件不存在"})
		return
	}
	defer obj.Close()

	c.Header("Content-Disposition", "inline; filename="+filename)
	c.Header("Content-Length", fmt.Sprintf("%d", size))
	c.Header("Content-Type", "application/pdf") // 简易处理

	io.Copy(c.Writer, obj)
}
