package service

import (
	"Chimera/backend-go/internal/data"
	"Chimera/backend-go/internal/dto"
	"Chimera/backend-go/internal/model"
	"context"
	"errors"
)

type KBService struct {
	Data *data.Data
}

func NewKBService(data *data.Data) *KBService {
	return &KBService{Data: data}
}

// CreateKnowledgeBase 创建知识库
func (s *KBService) CreateKnowledgeBase(ctx context.Context, userID uint, req dto.CreateKBReq) (*dto.KBResp, error) {
	var orgIDPtr *uint
	if req.OrgID > 0 {
		val := req.OrgID
		orgIDPtr = &val
	}

	// 1. 构造模型
	kb := &model.KnowledgeBase{
		Name:        req.Name,
		Description: req.Description,
		CreatorID:   userID,
		OrgID:       orgIDPtr, // 传入指针 (nil 或 &id)
	}

	// 2. 权限/归属检查
	if req.OrgID > 0 {
		// --- 组织模式 ---
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
	} else {
		// --- 个人模式 ---
		// 逻辑保持简单，OrgID=0 即为个人
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
		Type:        "folder", // 暂时硬编码或从 req 获取（如果 DTO 还有的话）
		CreatorID:   kb.CreatorID,
		OrgID:       orgIDPtr,
		CreatedAt:   kb.CreatedAt,
	}, nil
}

// ListKnowledgeBases 获取列表
func (s *KBService) ListKnowledgeBases(ctx context.Context, userID uint, orgID uint) ([]dto.KBResp, error) {
	var kbs []model.KnowledgeBase
	db := s.Data.DB.Model(&model.KnowledgeBase{})

	if orgID > 0 {
		// 查组织库
		// 1. 检查成员资格
		var isMember int64
		s.Data.DB.Model(&model.OrganizationMember{}).
			Where("organization_id = ? AND user_id = ?", orgID, userID).
			Count(&isMember)
		if isMember == 0 {
			return nil, errors.New("权限不足")
		}
		// 2. 过滤
		db = db.Where("org_id = ?", orgID)
	} else {
		// 查个人库 (OrgID is NULL)
		db = db.Where("creator_id = ? AND org_id IS NULL", userID)
	}

	if err := db.Order("created_at desc").Find(&kbs).Error; err != nil {
		return nil, err
	}

	var result []dto.KBResp
	for _, k := range kbs {
		result = append(result, dto.KBResp{
			ID:          k.ID,
			Name:        k.Name,
			Description: k.Description,
			Type:        "folder",
			CreatorID:   k.CreatorID,
			OrgID:       k.OrgID,
			CreatedAt:   k.CreatedAt,
		})
	}
	return result, nil
}
