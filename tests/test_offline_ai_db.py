import tempfile
import unittest
from pathlib import Path

from offline_ai_db import AIRecord, MultiAIDatabase


class TestMultiAIDatabase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_file = Path(self.tmpdir.name) / "test.db"
        self.db = MultiAIDatabase(self.db_file)

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def test_add_and_list(self):
        record_id = self.db.add_ai(
            AIRecord(
                name="VisionBot",
                provider="LocalLab",
                description="Image analysis assistant",
                capabilities="vision,ocr",
                tags="offline,image",
            )
        )
        self.assertGreater(record_id, 0)
        rows = self.db.list_all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "VisionBot")

    def test_bulk_add_and_search(self):
        count = self.db.bulk_add(
            [
                AIRecord("MathAI", "EdgeCorp", "Math solver", "reasoning,algebra", "offline,math"),
                AIRecord("CodeAI", "EdgeCorp", "Code helper", "coding,debug", "offline,dev"),
            ]
        )
        self.assertEqual(count, 2)

        results = self.db.search("coding OR algebra")
        names = [r["name"] for r in results]
        self.assertIn("MathAI", names)
        self.assertIn("CodeAI", names)

    def test_remove(self):
        rid = self.db.add_ai(
            AIRecord("ChatAI", "EdgeCorp", "Chat assistant", "chat,qa", "offline,nlp")
        )
        self.assertTrue(self.db.remove(rid))
        self.assertEqual(self.db.list_all(), [])


if __name__ == "__main__":
    unittest.main()
