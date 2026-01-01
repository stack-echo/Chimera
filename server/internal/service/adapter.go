package service

import (
	pb "Chimera/server/api/runtime/v1"
	"context"
)

type RuntimeAdapter struct {
	client pb.RuntimeServiceClient
}

func NewRuntimeAdapter(client pb.RuntimeServiceClient) *RuntimeAdapter {
	return &RuntimeAdapter{client: client}
}

func (a *RuntimeAdapter) SyncDataSource(ctx context.Context, req *pb.SyncRequest) (*pb.SyncResponse, error) {
	return a.client.SyncDataSource(ctx, req)
}

// StreamChat 方法
func (a *RuntimeAdapter) StreamChat(ctx context.Context, req *pb.RunAgentRequest) (pb.RuntimeService_RunAgentClient, error) {
	return a.client.RunAgent(ctx, req)
}
