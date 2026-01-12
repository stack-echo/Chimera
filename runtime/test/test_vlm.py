import logging
import time
from skills.vlm_service import VLMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VLM-Check")

def test_vlm():
    logger.info("🚀 启动 vLLM 真实推理测试...")

    try:
        vlm = VLMService.get_instance()

        # 🧪 找一张本地图片进行测试（如果没有，代码会跳过推理部分）
        # 建议你在 runtime 目录下放一张 test.jpg
        test_img = "test.jpg"

        if os.path.exists(test_img):
            logger.info(f"📸 正在解析测试图片: {test_img}")
            result = vlm.describe_image(test_img)
            logger.info(f"🤖 AI 描述结果: {result}")
            print("\n" + "="*30)
            print(f"🎉 最终成品验证成功！AI 描述: {result}")
            print("="*30)
        else:
            logger.warning("⚠️ 未找到 test.jpg，仅完成模型加载测试。")

    except Exception as e:
        logger.error(f"💥 测试失败: {e}")

if __name__ == "__main__":
    import os
    test_vlm()