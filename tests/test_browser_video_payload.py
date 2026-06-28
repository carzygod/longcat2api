import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


def load_browser_client_module():
    if "playwright" not in sys.modules:
        sys.modules["playwright"] = types.ModuleType("playwright")
    async_api = types.ModuleType("playwright.async_api")
    async_api.async_playwright = lambda: None
    async_api.BrowserContext = object
    async_api.Page = object
    sys.modules["playwright.async_api"] = async_api

    stealth_module = types.ModuleType("playwright_stealth")

    class Stealth:
        async def apply_stealth_async(self, _page):
            return None

    stealth_module.Stealth = Stealth
    sys.modules["playwright_stealth"] = stealth_module

    module_path = Path(__file__).resolve().parents[1] / "doubao2api" / "browser_client.py"
    spec = importlib.util.spec_from_file_location("browser_client", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


browser_client = load_browser_client_module()


class BrowserVideoPayloadTest(unittest.TestCase):
    def test_samantha_conversation_id_is_found_recursively(self):
        event = {
            "event_data": json.dumps({
                "message": json.dumps({
                    "content": "{}",
                    "conversation_id": "74881234567890",
                })
            })
        }

        self.assertEqual(
            browser_client.BrowserClient._find_samantha_conversation_id(event),
            "74881234567890",
        )

    def test_video_acceptance_text_detects_current_chinese_copy(self):
        message = "正在为您生成视频，本次使用 Seedance 2.0 Fast 生成，预计等待 1-3分钟。视频生成好后，我会主动发送给你。"

        self.assertTrue(browser_client.BrowserClient._is_video_acceptance_text(message))

    def test_video_quota_exhausted_text_is_not_acceptance(self):
        message = "正在为您生成视频...\n\n今日视频生成免费次数已用完。开通豆包专业版加强套餐，即可继续使用视频生成。"

        self.assertTrue(browser_client.BrowserClient._is_video_terminal_failure_text(message))
        self.assertFalse(browser_client.BrowserClient._is_video_acceptance_text(message))

    def test_video_message_contains_all_reference_attachments(self):
        message = browser_client.BrowserClient._build_video_message(
            prompt="animate",
            ratio="16:9",
            image_keys=["tos-a", "tos-b"],
            model="seedance_v2.0",
            duration=5,
        )

        content = json.loads(message["content"])
        self.assertEqual(content["ref_image_key"], "tos-a")
        self.assertEqual(content["reference_image_keys"], ["tos-a", "tos-b"])
        self.assertEqual(
            [item["image_token"] for item in content["samantha_context"]["query_context"]["ref_images"]],
            ["tos-a", "tos-b"],
        )
        self.assertEqual(
            message["attachments"],
            [
                {
                    "type": "image",
                    "key": "tos-a",
                    "url": "",
                    "extra": {"refer_types": "overall"},
                    "identifier": message["attachments"][0]["identifier"],
                },
                {
                    "type": "image",
                    "key": "tos-b",
                    "url": "",
                    "extra": {"refer_types": "overall"},
                    "identifier": message["attachments"][1]["identifier"],
                },
            ],
        )

    def test_video_message_preserves_uploaded_image_url_for_samantha_context(self):
        message = browser_client.BrowserClient._build_video_message(
            prompt="animate",
            ratio="1:1",
            image_keys=["tos-a"],
            model="seedance_v2.0",
            duration=5,
            image_attachments=[{
                "uri": "tos-a",
                "cdn_url": "https://example.com/a.png",
                "name": "a.png",
                "width": 320,
                "height": 240,
            }],
        )

        content = json.loads(message["content"])
        ref_image = content["samantha_context"]["query_context"]["ref_images"][0]
        self.assertEqual(ref_image["image_token"], "tos-a")
        self.assertEqual(ref_image["url"], "https://example.com/a.png")
        self.assertEqual(ref_image["image_ori"]["width"], 320)
        self.assertEqual(message["attachments"][0]["url"], "https://example.com/a.png")

    def test_chat_content_blocks_include_visible_image_attachment(self):
        blocks = browser_client.BrowserClient._build_chat_content_blocks(
            "animate this image",
            image_attachments=[{
                "uri": "ocean-cloud-tos/pages_upload_image_a.png",
                "cdn_url": "https://example.com/a.png",
                "name": "a.png",
                "format": "png",
                "width": 320,
                "height": 240,
            }],
        )

        self.assertEqual(blocks[0]["block_type"], 10052)
        attachment = blocks[0]["content"]["attachment_block"]["attachments"][0]
        self.assertEqual(attachment["type"], 2)
        self.assertEqual(attachment["image"]["uri"], "ocean-cloud-tos/pages_upload_image_a.png")
        self.assertEqual(attachment["image"]["image_ori"]["url"], "https://example.com/a.png")
        self.assertEqual(attachment["image"]["image_ori"]["width"], 320)
        self.assertEqual(attachment["extra"], {"refer_types": "overall"})
        self.assertEqual(blocks[1]["content"]["text_block"]["text"], "animate this image")

    def test_video_chat_attachment_blocks_match_web_ui_shape(self):
        blocks = browser_client.BrowserClient._build_chat_attachment_blocks(
            image_attachments=[{
                "uri": "tos-cn-i-a9rns2rl98/ref.png",
                "cdn_url": "",
                "name": "ref.png",
                "format": "png",
                "width": 1254,
                "height": 1254,
                "review_state": 1,
            }],
            attachment_type=1,
        )

        attachment = blocks[0]["content"]["attachment_block"]["attachments"][0]
        self.assertEqual(attachment["type"], 1)
        self.assertNotIn("extra", attachment)
        self.assertEqual(attachment["image"]["uri"], "tos-cn-i-a9rns2rl98/ref.png")
        self.assertEqual(attachment["image"]["image_ori"]["width"], 1254)
        self.assertEqual(attachment["review_state"], 1)

    def test_image_dimensions_read_png_header(self):
        png_header = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            b"\x00\x00\x04\xe6"
            b"\x00\x00\x02\xd0"
            b"\x08\x06\x00\x00\x00"
        )

        self.assertEqual(
            browser_client.BrowserClient._image_dimensions(png_header),
            (1254, 720),
        )

    def test_reference_image_infos_are_preserved_as_attachments(self):
        attachments = browser_client.BrowserClient._normalize_reference_image_attachments(
            ref_image_key="tos-a",
            reference_image_keys=["tos-b"],
            reference_image_infos=[{
                "uri": "tos-a",
                "cdn_url": "https://example.com/a.png",
                "name": "a.png",
            }],
        )

        self.assertEqual([item["uri"] for item in attachments], ["tos-a", "tos-b"])
        self.assertEqual(attachments[0]["cdn_url"], "https://example.com/a.png")


if __name__ == "__main__":
    unittest.main()
