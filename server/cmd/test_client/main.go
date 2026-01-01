package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"time"

	pb "Chimera/api/runtime/v1"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func main() {
	// 1. 连接 Python 服务 (localhost:50051)
	// 使用 insecure (非加密) 模式，因为是内部通信
	conn, err := grpc.Dial("localhost:50051", grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("无法连接 Chimera 大脑: %v", err)
	}
	defer conn.Close()

	// 2. 创建客户端
	client := pb.NewLLMServiceClient(conn)

	// 3. 构造请求
	req := &pb.AskRequest{
		Query:     "什么是三氯硅烷？",
		SessionId: "test-session-001",
		UseGraph:  true, // 开启图谱增强，测试 Python 端的 mock 逻辑
	}

	fmt.Printf("正在发送请求: %s\n", req.Query)

	// 4. 调用流式接口
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	stream, err := client.AskStream(ctx, req)
	if err != nil {
		log.Fatalf("调用失败: %v", err)
	}

	// 5. 循环读取流式响应
	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			break // 流结束
		}
		if err != nil {
			log.Fatalf("读取流失败: %v", err)
		}

		// 打印接收到的内容
		if resp.ThinkingLog != "" {
			fmt.Printf("\n[🧠 思考]: %s", resp.ThinkingLog)
		}
		if resp.AnswerDelta != "" {
			fmt.Printf("%s", resp.AnswerDelta) // 不换行，模拟打字机
		}
		if len(resp.SourceDocs) > 0 {
			fmt.Printf("\n\n[📚 引用]: %s (页码: %s)", resp.SourceDocs[0].DocName, resp.SourceDocs[0].PageNum)
		}
	}
	fmt.Println("\n\n--- 对话结束 ---")
}
