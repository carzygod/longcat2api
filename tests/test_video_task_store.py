import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "doubao2api" / "video_tasks.py"
SPEC = importlib.util.spec_from_file_location("video_tasks", MODULE_PATH)
video_tasks = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(video_tasks)
VideoTaskStore = video_tasks.VideoTaskStore


class VideoTaskStoreTest(unittest.TestCase):
    def test_create_update_and_read_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "video_tasks.sqlite3"
            store = VideoTaskStore(str(db_path))

            task = store.create(
                "video-test",
                {
                    "prompt": "white cube",
                    "model": "doubao-video",
                    "provider_model": "seedance_v2.0",
                    "ratio": "16:9",
                    "duration": 10,
                    "ref_image_key": None,
                    "reference_image_keys": ["tos-a", "tos-b"],
                },
                {"prompt": "white cube", "duration": 10},
            )

            self.assertEqual(task["status"], "queued")
            self.assertEqual(json.loads(task["reference_image_keys"]), ["tos-a", "tos-b"])
            self.assertEqual(store.counts(), {"queued": 1})

            result = {"data": [{"video_url": "https://example.com/video.mp4"}]}
            store.update(
                "video-test",
                "completed",
                result_json=json.dumps(result),
                account_id="second-account",
                ref_image_key="tos-final-a",
                reference_image_keys=json.dumps(["tos-final-a", "tos-final-b"]),
            )
            task = store.get("video-test")

            self.assertIsNotNone(task)
            self.assertEqual(task["status"], "completed")
            self.assertEqual(task["account_id"], "second-account")
            self.assertEqual(task["ref_image_key"], "tos-final-a")
            self.assertEqual(json.loads(task["reference_image_keys"]), ["tos-final-a", "tos-final-b"])
            self.assertEqual(json.loads(task["result_json"]), result)

    def test_mark_interrupted_tasks_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "video_tasks.sqlite3"
            store = VideoTaskStore(str(db_path))
            store.create(
                "video-interrupted",
                {"prompt": "white cube", "model": "doubao-video"},
                {"prompt": "white cube"},
            )

            store.mark_interrupted()
            task = store.get("video-interrupted")

            self.assertIsNotNone(task)
            self.assertEqual(task["status"], "failed")
            self.assertIn("server restarted", task["error"])


if __name__ == "__main__":
    unittest.main()
