package service

import (
	"Chimera/backend-go/internal/dto"
	"Chimera/backend-go/internal/model"
	"Chimera/backend-go/internal/repository"
	"Chimera/backend-go/internal/utils" // 引用你写的 utils
	"errors"
)

type AuthService interface {
	Register(req dto.RegisterReq) (uint, error)
	Login(req dto.LoginReq) (*dto.LoginResp, error)
}

type authService struct {
	repo repository.UserRepository
}

func NewAuthService(repo repository.UserRepository) AuthService {
	return &authService{repo: repo}
}

// Register 注册业务逻辑
func (s *authService) Register(req dto.RegisterReq) (uint, error) {
	// 1. 业务检查：用户名是否存在
	if s.repo.IsUsernameExist(req.Username) {
		return 0, errors.New("用户名已存在")
	}

	// 2. 密码加密
	hash, err := utils.HashPassword(req.Password)
	if err != nil {
		return 0, errors.New("密码加密失败")
	}

	// 3. 组装 Model
	user := &model.User{
		Username:     req.Username,
		PasswordHash: hash,
		Email:        req.Email,
		Role:         "user",
	}

	// 4. 落库
	if err := s.repo.Create(user); err != nil {
		return 0, err
	}

	return user.ID, nil
}

// Login 登录业务逻辑
func (s *authService) Login(req dto.LoginReq) (*dto.LoginResp, error) {
	// 1. 查用户
	user, err := s.repo.GetByUsername(req.Username)
	if err != nil {
		return nil, errors.New("用户不存在")
	}

	// 2. 比对密码
	if !utils.CheckPasswordHash(req.Password, user.PasswordHash) {
		return nil, errors.New("密码错误")
	}

	// 3. 签发 Token
	token, err := utils.GenerateToken(user.ID, user.Username, user.Role)
	if err != nil {
		return nil, errors.New("Token 生成失败")
	}

	return &dto.LoginResp{
		Token:    token,
		Username: user.Username,
		UserID:   user.ID,
	}, nil
}
