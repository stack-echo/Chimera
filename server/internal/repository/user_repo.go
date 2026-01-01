package repository

import (
	"Chimera/server/internal/model"
	"gorm.io/gorm"
)

type UserRepository interface {
	Create(user *model.User) error
	GetByUsername(username string) (*model.User, error)
	IsUsernameExist(username string) bool
}

type userRepository struct {
	db *gorm.DB
}

func NewUserRepository(db *gorm.DB) UserRepository {
	return &userRepository{db: db}
}

func (r *userRepository) Create(user *model.User) error {
	return r.db.Create(user).Error
}

func (r *userRepository) GetByUsername(username string) (*model.User, error) {
	var user model.User
	if err := r.db.Where("username = ?", username).First(&user).Error; err != nil {
		return nil, err
	}
	return &user, nil
}

func (r *userRepository) IsUsernameExist(username string) bool {
	var count int64
	r.db.Model(&model.User{}).Where("username = ?", username).Count(&count)
	return count > 0
}
