package dto

type FileResp struct {
	ID        uint   `json:"id"`
	Title     string `json:"title"`
	FileName  string `json:"file_name"`
	Size      int64  `json:"size"`
	Status    string `json:"status"` // pending, parsing, success
	CreatedAt string `json:"created_at"`
}
