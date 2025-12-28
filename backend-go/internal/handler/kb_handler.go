package handler

import (
	"Chimera-RAG/backend-go/internal/dto"
	"Chimera-RAG/backend-go/internal/service"
	"github.com/gin-gonic/gin"
	"net/http"
	"strconv"
)

type KBHandler struct {
	svc *service.KBService
}

func NewKBHandler(svc *service.KBService) *KBHandler {
	return &KBHandler{svc: svc}
}

// Create 创建知识库
// POST /api/v1/kbs
func (h *KBHandler) Create(c *gin.Context) {
	var req dto.CreateKBReq
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	userID, exists := c.Get("userID")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "未登录"})
		return
	}

	resp, err := h.svc.CreateKnowledgeBase(c.Request.Context(), userID.(uint), req)
	if err != nil {
		// 区分一下是权限错误还是服务器错误会更好，这里暂时简化
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"data": resp})
}

// List 获取知识库列表
// GET /api/v1/kbs?org_id=1
func (h *KBHandler) List(c *gin.Context) {
	userID, exists := c.Get("userID")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "未登录"})
		return
	}

	// 获取 Query 参数，默认为空字符串
	orgIDStr := c.Query("org_id")
	var orgID uint = 0

	// 如果传了参数，尝试转为 uint
	if orgIDStr != "" {
		// 这里偷懒用了简单的转换，生产环境可以用 cast 库
		// 或者直接定义一个 Form 结构体用 ShouldBindQuery
		if id, err := strconv.Atoi(orgIDStr); err == nil {
			orgID = uint(id)
		}
	}

	list, err := h.svc.ListKnowledgeBases(c.Request.Context(), userID.(uint), orgID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"data": list})
}
