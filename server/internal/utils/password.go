package utils

import (
	"golang.org/x/crypto/bcrypt"
)

// HashPassword 将明文密码加密为 Hash 字符串
// 用于：用户注册 (Register)
func HashPassword(password string) (string, error) {
	// GenerateFromPassword 会自动加盐 (Salt)，即使两个用户密码相同，生成的 Hash 也不同
	// DefaultCost 目前是 10，是一个在性能和安全性之间平衡的值
	bytes, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	return string(bytes), err
}

// CheckPasswordHash 校验明文密码是否与 Hash 匹配
// 用于：用户登录 (Login)
// 返回 true 表示密码正确，false 表示错误
func CheckPasswordHash(password, hash string) bool {
	err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(password))
	return err == nil
}
