package model

type Document struct {
	BaseModel
	Title    string `gorm:"index" json:"title"`
	FileName string `json:"file_name"`
	FileSize int64  `json:"file_size"`
	FileType string `json:"file_type"`

	// 冗余字段，方便快速鉴权
	OwnerID uint `gorm:"index"`

	// minio://bucket/path
	StoragePath string `gorm:"not null" json:"storage_path"`

	KnowledgeBaseID uint `gorm:"index;not null" json:"knowledge_base_id"`

	// 状态机
	Status   string `gorm:"default:'pending';index" json:"status"`
	ErrorMsg string `json:"error_msg"`

	// 解析元数据
	ParserType string `gorm:"default:'docling'" json:"parser_type"`
	ChunkCount int    `json:"chunk_count"`

	// v0.3.5 新增：页数 (Docling 解析出来后回填)
	PageCount int `json:"page_count"`
}
