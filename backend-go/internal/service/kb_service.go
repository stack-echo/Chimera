package service

import (
	"Chimera-RAG/backend-go/internal/data"
	"Chimera-RAG/backend-go/internal/dto"
	"Chimera-RAG/backend-go/internal/model"
	"context"
	"errors"
)

type KBService struct {
	Data *data.Data
}

func NewKBService(data *data.Data) *KBService {
	return &KBService{Data: data}
}

// CreateKnowledgeBase 创建知识库 (支持 个人/组织 双模式)
func (s *KBService) CreateKnowledgeBase(ctx context.Context, userID uint, req dto.CreateKBReq) (*dto.KBResp, error) {
	kb := &model.KnowledgeBase{
		Name:        req.Name,
		Description: req.Description,
		Type:        req.Type,
		CreatorID:   userID, // 无论归属谁，创建者永远是你
		IsPublic:    false,  // 默认为私有
	}

	// 🔥 核心分支逻辑
	if req.OrgID > 0 {
		// --- 🅰️ 组织模式 ---

		// 1. 安全检查：你必须是该组织的成员才能创建
		var count int64
		err := s.Data.DB.Model(&model.OrganizationMember{}).
			Where("organization_id = ? AND user_id = ?", req.OrgID, userID).
			Count(&count).Error
		if err != nil {
			return nil, err
		}
		if count == 0 {
			return nil, errors.New("权限不足：你不是该组织的成员")
		}

		// 2. 绑定组织 ID
		orgID := req.OrgID
		kb.OrgID = &orgID // 赋值指针

	} else {
		// --- 🅱️ 个人模式 ---
		kb.OrgID = nil // 明确设为 nil
	}

	// 3. 落库
	if err := s.Data.DB.Create(kb).Error; err != nil {
		return nil, err
	}

	// 4. 返回结果
	return &dto.KBResp{
		ID:          kb.ID,
		Name:        kb.Name,
		Description: kb.Description,
		Type:        kb.Type,
		CreatorID:   kb.CreatorID,
		OrgID:       kb.OrgID,
		CreatedAt:   kb.CreatedAt,
	}, nil
}

// ListKnowledgeBases 获取知识库列表 (根据 orgID 过滤)
func (s *KBService) ListKnowledgeBases(ctx context.Context, userID uint, orgID uint) ([]dto.KBResp, error) {
	var kbs []model.KnowledgeBase

	db := s.Data.DB.Model(&model.KnowledgeBase{})

	if orgID > 0 {
		// --- 🅰️ 组织模式 ---
		// 1. 安全检查：你必须是该组织成员才能查看该组织的知识库
		var isMember int64
		s.Data.DB.Model(&model.OrganizationMember{}).
			Where("organization_id = ? AND user_id = ?", orgID, userID).
			Count(&isMember)

		if isMember == 0 {
			return nil, errors.New("权限不足：你不是该组织的成员")
		}

		// 2. 查询条件：该组织下的所有 KB
		db = db.Where("org_id = ?", orgID)
	} else {
		// --- 🅱️ 个人模式 ---
		// 查询条件：我自己创建的，且不属于任何组织的
		db = db.Where("creator_id = ? AND org_id IS NULL", userID)
	}

	// 执行查询 (按创建时间倒序)
	if err := db.Order("created_at desc").Find(&kbs).Error; err != nil {
		return nil, err
	}

	// 转换为 DTO
	var result []dto.KBResp
	for _, k := range kbs {
		result = append(result, dto.KBResp{
			ID:          k.ID,
			Name:        k.Name,
			Description: k.Description,
			Type:        k.Type,
			CreatorID:   k.CreatorID,
			OrgID:       k.OrgID,
			CreatedAt:   k.CreatedAt,
		})
	}

	return result, nil
}
