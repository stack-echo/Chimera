package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"strings"
	"time"

	pb "Chimera/server/api/runtime/v1"
	"Chimera/server/internal/data"
	"Chimera/server/internal/dto"
	"Chimera/server/internal/model"
)

// ChatService
// 职责：只专注于对话流、历史记录、日志审计
type ChatService struct {
	Data    *data.Data
	Adapter *RuntimeAdapter
}

// NewChatService 构造函数
func NewChatService(data *data.Data, adapter *RuntimeAdapter) *ChatService {
	return &ChatService{
		Data:    data,
		Adapter: adapter,
	}
}

// StreamChat 处理对话请求
func (s *ChatService) StreamChat(ctx context.Context, userID uint, req dto.ChatReq, respChan chan<- string) {
	defer close(respChan)

	// 1. 鉴权
	if req.KbID > 0 {
		if err := s.checkKbPermission(req.KbID, userID); err != nil {
			respChan <- fmt.Sprintf("ERR: ⛔️ %s", err.Error())
			return
		}
	}

	// 2. 构造配置给 Python
	configData := map[string]interface{}{
		"kb_ids": []uint{req.KbID},
		"org_id": req.OrgID,
	}
	configBytes, _ := json.Marshal(configData)

	grpcReq := &pb.RunAgentRequest{
		AppId:         "default_chat_app",
		Query:         req.Query,
		SessionId:     req.SessionID,
		AppConfigJson: string(configBytes),
	}

	// 3. 调用 Adapter
	stream, err := s.Adapter.StreamChat(ctx, grpcReq)
	if err != nil {
		log.Printf("❌ gRPC Link Error: %v", err)
		respChan <- "ERR: 服务端连接失败"
		return
	}

	// 4. 处理流响应
	var fullAnswerBuilder strings.Builder
	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			log.Printf("❌ gRPC Recv Error: %v", err)
			return
		}

		switch resp.Type {
		case "delta":
			respChan <- resp.Payload
			fullAnswerBuilder.WriteString(resp.Payload)
		case "thought":
			respChan <- "THOUGHT: " + resp.Payload
		case "reference":
			respChan <- "REF: " + resp.Payload
		case "summary":
			go s.saveRunLog(userID, req, resp.Summary, fullAnswerBuilder.String())
		case "error":
			respChan <- "\n[Error]: " + resp.Payload
		}
	}
}

// checkKbPermission 私有鉴权 (ChatService 独享)
func (s *ChatService) checkKbPermission(kbID uint, userID uint) error {
	var kb model.KnowledgeBase
	if err := s.Data.DB.First(&kb, kbID).Error; err != nil {
		return errors.New("知识库不存在")
	}
	if kb.OrgID != nil {
		var count int64
		s.Data.DB.Model(&model.OrganizationMember{}).
			Where("organization_id = ? AND user_id = ?", *kb.OrgID, userID).
			Count(&count)
		if count == 0 {
			return errors.New("无权访问该组织知识库")
		}
		return nil
	}
	if kb.CreatorID != userID {
		return errors.New("无权访问该知识库")
	}
	return nil
}

// saveRunLog 日志落库
func (s *ChatService) saveRunLog(userID uint, req dto.ChatReq, summary *pb.RunSummary, answer string) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	runLog := &model.AppRunLog{
		OrgID:            req.OrgID,
		AppID:            "default_chat_app",
		UserID:           userID,
		SessionID:        req.SessionID,
		Query:            req.Query,
		Answer:           answer,
		TotalTokens:      int(summary.TotalTokens),
		PromptTokens:     int(summary.PromptTokens),
		CompletionTokens: int(summary.CompletionTokens),
		DurationMs:       summary.TotalDurationMs,
		Status:           summary.FinalStatus,
	}

	if err := s.Data.DB.WithContext(ctx).Create(runLog).Error; err != nil {
		log.Printf("❌ 日志入库失败: %v", err)
	}
}
