package handler

import (
	"Chimera/server/internal/dto"
	"Chimera/server/internal/service"
	"github.com/gin-gonic/gin"
	"net/http"
)

type DataSourceHandler struct {
	svc *service.DataSourceService
}

func NewDataSourceHandler(svc *service.DataSourceService) *DataSourceHandler {
	return &DataSourceHandler{svc: svc}
}

func (h *DataSourceHandler) Create(c *gin.Context) {
	var req dto.CreateDataSourceReq
	// 绑定 JSON
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	userID := c.GetUint("userID")

	// 🔥 改造点：直接调用通用接口
	ds, err := h.svc.CreateDataSource(c.Request.Context(), userID, req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"data": ds})
}
