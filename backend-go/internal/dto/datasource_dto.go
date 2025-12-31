package dto

type CreateDataSourceReq struct {
	KbID uint   `json:"kb_id" binding:"required"`
	Type string `json:"type" binding:"required,oneof=feishu_wiki dingtalk web"`
	Name string `json:"name" binding:"required"`

	// 飞书特有配置
	FeishuConfig FeishuConfig `json:"feishu_config"`
}

type FeishuConfig struct {
	AppID       string `json:"app_id"`
	AppSecret   string `json:"app_secret"`
	WikiSpaceID string `json:"wiki_space_id"`
}