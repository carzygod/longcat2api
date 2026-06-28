import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "doubao2api" / "unified_server.py"


def load_quota_helper():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    helpers = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"is_quota_exhaustion_message", "is_video_acceptance_message"}
    ]
    module = ast.Module(
        body=[
            ast.Import(names=[ast.alias(name="re")]),
            *helpers,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(MODULE_PATH), "exec"), namespace)
    return namespace


helpers = load_quota_helper()
is_quota_exhaustion_message = helpers["is_quota_exhaustion_message"]
is_video_acceptance_message = helpers["is_video_acceptance_message"]


class VideoQuotaErrorTest(unittest.TestCase):
    def test_positive_remaining_quota_message_is_not_exhausted(self):
        self.assertFalse(
            is_quota_exhaustion_message(
                "本次使用 Seedance 2.0 全能视频模型生成，今日剩余 9 个视频生成额度。"
            )
        )

    def test_zero_or_insufficient_quota_message_is_exhausted(self):
        self.assertTrue(is_quota_exhaustion_message("今日剩余 0 个视频生成额度"))
        self.assertTrue(is_quota_exhaustion_message("视频生成额度不足"))
        self.assertTrue(is_quota_exhaustion_message("quota exceeded"))

    def test_video_acceptance_message_is_detected(self):
        self.assertTrue(
            is_video_acceptance_message(
                "正在为您生成视频，预计等待 1-3分钟。视频生成好后，我会及时通知你。"
            )
        )
        self.assertFalse(is_video_acceptance_message("视频生成额度不足"))


    def test_real_chinese_free_video_quota_exhausted_message_is_failed(self):
        message = "正在为您生成视频...\n\n今日视频生成免费次数已用完。开通豆包专业版加强套餐，即可继续使用视频生成。"
        self.assertTrue(is_quota_exhaustion_message(message))

    def test_real_chinese_free_video_quota_exhausted_message_is_not_accepted(self):
        message = "正在为您生成视频...\n\n今日视频生成免费次数已用完。开通豆包专业版加强套餐，即可继续使用视频生成。"
        self.assertFalse(is_video_acceptance_message(message))


if __name__ == "__main__":
    unittest.main()
