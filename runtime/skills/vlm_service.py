import os
import logging
from PIL import Image
from vllm import LLM, SamplingParams
from config import Config

# WSL2 环境优化
os.environ["VLLM_USE_MODELSCOPE"] = "True"
os.environ["NCCL_P2P_DISABLE"] = "1"
os.environ["NCCL_IB_DISABLE"] = "1"

logger = logging.getLogger(__name__)

class VLMService:
    _instance = None

    def __init__(self):
        self.model_path = Config.VLM_MODEL_PATH
        logger.info(f"🎨 [vLLM] 正在 A4000 启动自适应视觉引擎: {self.model_path}")

        try:
            # 💡 针对 16GB 显存的最终平衡方案
            self.model = LLM(
                model=self.model_path,
                trust_remote_code=True,
                # 🔥 调整 1：利用率提升到 0.7 (约 11.2GB)，给 KV Cache 留足空间
                gpu_memory_utilization=0.7,
                # 🔥 调整 2：上限提升到 2048，足以容纳缩放后的图片
                max_model_len=2048,
                limit_mm_per_prompt={"image": 1},
                enforce_eager=True
            )

            self.sampling_params = SamplingParams(
                temperature=0.1,
                top_p=0.9,
                max_tokens=512,
                stop=["<|endoftext|>", "<|im_end|>"]
            )
            logger.info("✅ vLLM 视觉引擎已成功入驻并完成自适应配置！")
        except Exception as e:
            logger.error(f"❌ vLLM 初始化失败: {e}")
            raise e

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def describe_image(self, image_path: str, context_breadcrumb: str = "", is_table: bool = False) -> str:
        """
        带上下文引导的视觉推理
        """
        # 💡 针对不同类型的图，使用不同的引导语
        if is_table:
            prompt = (
                "这是一张从学术论文中提取的表格图片。"
                "1. 请首先在图片中寻找类似 'Table 1', 'Table 2' 的文字标识，并以此作为开头。"
                "2. 请将表格内容完整、精确地转录为 Markdown 格式。"
                "3. 严禁概括，必须保留每一行、每一列的原始数值和单位。"
                f"4. 参考上下文：该图可能位于文档的 {context_breadcrumb} 章节。"
            )
        else:
            prompt = f"这张图片位于 '{context_breadcrumb}'。请详细识别图中的架构组件、箭头流向、文字说明。如果是流程图，请列出从 A 到 B 的具体步骤。"

        input_prompt = (
            f"<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n"
            f"<|im_start|>user\n<|vision_start|><|image_pad|><|vision_end|>{prompt}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        try:
            # 手动缩放图片防止 Token 溢出
            # Qwen2-VL 每个 28x28 的切片是一个 Token
            # 限制总像素在 250,000 左右（约等于 500x500），产生约 400-600 个 Token
            raw_image = Image.open(image_path).convert("RGB")

            # 动态计算缩放比例
            max_pixels = 600000
            width, height = raw_image.size
            if width * height > max_pixels:
                scale = (max_pixels / (width * height)) ** 0.5
                new_size = (int(width * scale), int(height * scale))
                image = raw_image.resize(new_size, Image.LANCZOS)
                logger.info(f"📏 图片已从 {width}x{height} 缩放至 {new_size}")
            else:
                image = raw_image

            outputs = self.model.generate(
                {
                    "prompt": input_prompt,
                    "multi_modal_data": {"image": image},
                },
                sampling_params=self.sampling_params
            )
            return outputs[0].outputs[0].text
        except Exception as e:
            logger.error(f"❌ 推理失败: {e}")
            return f"[视觉解析异常]: {str(e)}"