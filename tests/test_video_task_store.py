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
                    "conversation_id": "38432920697854722",
                    "provider_task_id": "provider-video-task",
                    "quota_reservation_id": "usage-1",
                    "quota_units": 2,
                },
                {"prompt": "white cube", "duration": 10},
            )

            self.assertEqual(task["status"], "queued")
            self.assertEqual(json.loads(task["reference_image_keys"]), ["tos-a", "tos-b"])
            self.assertEqual(task["conversation_id"], "38432920697854722")
            self.assertEqual(task["provider_task_id"], "provider-video-task")
            self.assertEqual(task["quota_reservation_id"], "usage-1")
            self.assertEqual(task["quota_units"], 2)
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

    def test_mark_interrupted_keeps_accepted_pending_task_recoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "video_tasks.sqlite3"
            store = VideoTaskStore(str(db_path))
            store.create(
                "video-accepted-pending",
                {"prompt": "red square", "model": "doubao-video"},
                {"prompt": "red square"},
            )
            pending_result = {
                "data": [],
                "pending": True,
                "accepted": True,
                "message": "video generation accepted",
            }
            store.update(
                "video-accepted-pending",
                "in_progress",
                result_json=json.dumps(pending_result),
                message="video generation accepted",
            )

            store.mark_interrupted()
            task = store.get("video-accepted-pending")

            self.assertIsNotNone(task)
            self.assertEqual(task["status"], "in_progress")
            self.assertIsNone(task["error"])
            self.assertEqual(task["message"], "video generation accepted")
            self.assertEqual(json.loads(task["result_json"]), pending_result)

    def test_mark_interrupted_keeps_task_with_accepted_message_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "video_tasks.sqlite3"
            store = VideoTaskStore(str(db_path))
            store.create(
                "video-message-pending",
                {"prompt": "red square", "model": "doubao-video"},
                {"prompt": "red square"},
            )
            store.update(
                "video-message-pending",
                "in_progress",
                message="The service is generating video and will notify when ready.",
            )

            store.mark_interrupted()
            task = store.get("video-message-pending")

            self.assertIsNotNone(task)
            self.assertEqual(task["status"], "in_progress")
            self.assertIsNone(task["error"])
            self.assertEqual(
                task["message"],
                "The service is generating video and will notify when ready.",
            )

    def test_recovery_candidates_only_returns_accepted_pending_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "video_tasks.sqlite3"
            store = VideoTaskStore(str(db_path))
            store.create(
                "video-pending",
                {"prompt": "red square", "model": "doubao-video"},
                {"prompt": "red square"},
            )
            store.create(
                "video-plain",
                {"prompt": "blue square", "model": "doubao-video"},
                {"prompt": "blue square"},
            )
            store.update(
                "video-pending",
                "in_progress",
                result_json=json.dumps({"pending": True, "accepted": True}),
                message="video generation accepted",
                accepted_at=123,
            )
            store.update("video-plain", "in_progress", message="still working")

            candidates = store.recovery_candidates(min_interval_seconds=0)

            self.assertEqual([task["task_id"] for task in candidates], ["video-pending"])

    def test_normalize_completed_clears_stale_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "video_tasks.sqlite3"
            store = VideoTaskStore(str(db_path))
            store.create(
                "video-recovered",
                {"prompt": "red square", "model": "doubao-video"},
                {"prompt": "red square"},
            )
            store.update(
                "video-recovered",
                "completed",
                result_json=json.dumps({"data": [{"video_url": "https://example.com/video.mp4"}]}),
                error="old polling error",
            )

            store.normalize_completed()
            task = store.get("video-recovered")

            self.assertIsNotNone(task)
            self.assertEqual(task["status"], "completed")
            self.assertIsNone(task["error"])


if __name__ == "__main__":
    unittest.main()
