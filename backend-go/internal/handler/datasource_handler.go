package handler

import (
	"Chimera/backend-go/internal/dto"
	"Chimera/backend-go/internal/service"
	"github.com/gin-gonic/gin"
	"net/http"
)

type DataSourceHandler struct {
	svc *service.RuntimeService
}

func NewDataSourceHandler(svc *service.RuntimeService) *DataSourceHandler {
	return &DataSourceHandler{svc: svc}
}

func (h *DataSourceHandler) Create(c *gin.Context) {
	var req dto.CreateDataSourceReq
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	userID := c.GetUint("userID")

	// 这里目前只处理飞书，未来可以用 switch req.Type 处理更多
	ds, err := h.svc.CreateFeishuSource(c.Request.Context(), userID, req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"data": ds})
}