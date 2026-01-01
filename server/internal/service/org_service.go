package service

import (
	"Chimera/server/internal/data"
	"Chimera/server/internal/dto"
	"Chimera/server/internal/model"
	"context"
	"errors"
	"gorm.io/gorm"
	"math/rand"
)

type OrgService struct {
	Data *data.Data
}

func NewOrgService(data *data.Data) *OrgService {
	return &OrgService{Data: data}
}

// CreateOrganization 创建组织
func (s *OrgService) CreateOrganization(ctx context.Context, userID uint, req dto.CreateOrgReq) (*dto.OrgResp, error) {
	// 👇 自动补全逻辑
	if req.Key == "" {
		// 生成一个 8 位的随机 Key，例如 "xk9d2m1a"
		req.Key = generateRandomKey(8)
	}
	// 1. 检查 Key 是否已存在 (Key 必须唯一)
	var count int64
	s.Data.DB.Model(&model.Organization{}).Where("key = ?", req.Key).Count(&count)
	if count > 0 {
		return nil, errors.New("组织标识(Key)已存在，请换一个")
	}

	org := &model.Organization{
		Name:        req.Name,
		Description: req.Description,
		Key:         req.Key,
		OwnerID:     userID,
	}

	// 2. 开启事务：创建组织 + 添加成员
	err := s.Data.DB.Transaction(func(tx *gorm.DB) error {
		// A. 创建组织记录
		if err := tx.Create(org).Error; err != nil {
			return err
		}

		// B. 将创建者加入成员表，并设为 Owner
		member := &model.OrganizationMember{
			OrganizationID: org.ID,
			UserID:         userID,
			Role:           "owner",
		}
		if err := tx.Create(member).Error; err != nil {
			return err // 返回错误会触发回滚
		}

		return nil
	})

	if err != nil {
		return nil, err
	}

	// 3. 返回结果
	return &dto.OrgResp{
		ID:          org.ID,
		Name:        org.Name,
		Description: org.Description,
		Key:         org.Key,
		OwnerID:     org.OwnerID,
		CreatedAt:   org.CreatedAt,
	}, nil
}

// ListUserOrganizations 获取用户加入的所有组织
func (s *OrgService) ListUserOrganizations(ctx context.Context, userID uint) ([]dto.OrgResp, error) {
	var memberships []model.OrganizationMember

	// 1. 查询中间表，并预加载 Organization 实体
	// SELECT * FROM organization_members WHERE user_id = ?
	if err := s.Data.DB.
		Preload("Organization").
		Where("user_id = ?", userID).
		Find(&memberships).Error; err != nil {
		return nil, err
	}

	// 2. 转换为 DTO
	var result []dto.OrgResp
	for _, m := range memberships {
		// 稍微防御一下，万一组织被删了但中间表还在
		if m.Organization.ID == 0 {
			continue
		}

		result = append(result, dto.OrgResp{
			ID:          m.Organization.ID,
			Name:        m.Organization.Name,
			Description: m.Organization.Description,
			Key:         m.Organization.Key,
			OwnerID:     m.Organization.OwnerID, // 注意：这里的 OwnerID 是组织的拥有者，不是当前用户
			CreatedAt:   m.Organization.CreatedAt,
			// 💡 可以在这里加一个 UserRole: m.Role 返回给前端，告诉前端我在这个组里是什么角色
		})
	}

	return result, nil
}

func generateRandomKey(n int) string {
	const letters = "abcdefghijklmnopqrstuvwxyz0123456789"
	b := make([]byte, n)
	for i := range b {
		b[i] = letters[rand.Intn(len(letters))]
	}
	return string(b)
}
