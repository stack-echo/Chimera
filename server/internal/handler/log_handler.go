package handler

import (
	"Chimera/server/internal/dto"
	"Chimera/server/internal/service"
	"github.com/gin-gonic/gin"
	"net/http"
)

type LogHandler struct {
	svc *service.LogService
}

func NewLogHandler(svc *service.LogService) *LogHandler {
	return &LogHandler{svc: svc}
}

// List 获取日志列表
// GET /api/v1/logs
func (h *LogHandler) List(c *gin.Context) {
	var req dto.LogListReq
	if err := c.ShouldBindQuery(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	userID := c.GetUint("userID")
	resp, err := h.svc.GetLogList(c.Request.Context(), userID, req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"data": resp})
}

// Stats 获取统计数据
// GET /api/v1/stats
func (h *LogHandler) Stats(c *gin.Context) {
	var req dto.AppStatsReq
	if err := c.ShouldBindQuery(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	resp, err := h.svc.GetAppStats(c.Request.Context(), req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"data": resp})
}
