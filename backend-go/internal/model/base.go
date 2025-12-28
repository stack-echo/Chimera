package model

import (
	"gorm.io/gorm"
	"time"
)

// StandardModel 替代 gorm.Model，方便自定义 JSON tag
type BaseModel struct {
	ID        uint           `gorm:"primarykey" json:"id"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
	DeletedAt gorm.DeletedAt `gorm:"index" json:"-"`
}
