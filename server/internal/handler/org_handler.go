package handler

import (
	"Chimera/server/internal/dto"
	"Chimera/server/internal/service"
	"github.com/gin-gonic/gin"
	"net/http"
)

type OrgHandler struct {
	svc *service.OrgService
}

func NewOrgHandler(svc *service.OrgService) *OrgHandler {
	return &OrgHandler{svc: svc}
}

// Create 创建组织
// POST /api/v1/orgs
func (h *OrgHandler) Create(c *gin.Context) {
	var req dto.CreateOrgReq
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 从中间件获取当前登录用户 ID
	userID, exists := c.Get("userID")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "未登录"})
		return
	}

	// 调用 Service
	// 注意：userID.(uint) 是类型断言，确保中间件里存的是 uint 类型
	resp, err := h.svc.CreateOrganization(c.Request.Context(), userID.(uint), req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"data": resp})
}

// List 获取我的组织列表
// GET /api/v1/orgs
func (h *OrgHandler) List(c *gin.Context) {
	userID, exists := c.Get("userID")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "未登录"})
		return
	}

	orgs, err := h.svc.ListUserOrganizations(c.Request.Context(), userID.(uint))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "获取组织列表失败"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"data": orgs})
}
