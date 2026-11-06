import tempfile
import unittest
from pathlib import Path

from data_store import DEFAULT_STATE, StateStore


class TestStateStore(unittest.TestCase):
    def test_defaults_and_persistence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "db" / "state.json"
            store = StateStore(path)
            self.assertEqual(store.get("schedule"), DEFAULT_STATE["schedule"])
            store.set("schedule", "Sobota 19:00")
            store.set("messages", {"schedule": 123})
            again = StateStore(path)
            self.assertEqual(again.get("schedule"), "Sobota 19:00")
            self.assertEqual(again.get("messages"), {"schedule": 123})
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_reject_unknown_state(self):
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "state.json")
            with self.assertRaises(KeyError):
                store.set("token", "secret")
            with self.assertRaises(TypeError):
                store.set("schedule", 123)

    def test_storage_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            store1 = StateStore(Path(temp) / "one.json")
            store1.set("schedule", "Poniedziałek")
            store2 = StateStore(Path(temp) / "two.json")
            self.assertNotEqual(store1.get("schedule"), store2.get("schedule"))


if __name__ == "__main__":
    unittest.main()
