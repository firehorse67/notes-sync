"""Integration tests for FileManager import/export against a throwaway notes dir.

HOME is redirected so the real metadata cache and config are never touched.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

_HOME = tempfile.mkdtemp(prefix="notes-sync-test-home-")
os.environ["HOME"] = _HOME

from notes_app import file_manager as fm_mod  # noqa: E402


class FileManagerIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.notes = os.path.join(self.tmp.name, "notes")
        os.makedirs(self.notes)
        with mock.patch.object(fm_mod, "ensure_notes_dir", return_value=self.notes):
            self.fm = fm_mod.FileManager()
        self.out = os.path.join(self.tmp.name, "out.json")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.notes, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def all_md(self, root=None):
        root = root or self.tmp.name
        found = []
        for r, _, files in os.walk(root):
            found += [os.path.relpath(os.path.join(r, f), root) for f in files if f.endswith(".md")]
        return sorted(found)

    def test_note_dict_reads_file_not_cold_cache(self):
        path = self.write("Work/Plan.md", "---\ntags: [q4]\npinned: true\n---\n# The Plan\n\nBody\n")
        d = self.fm.get_note_as_dict(path)
        self.assertEqual(d["tags"], ["q4"])
        self.assertTrue(d["pinned"])
        self.assertEqual(d["title"], "The Plan")
        self.assertEqual(d["notebook"], "Work")

    def test_legacy_project_import_cannot_escape_notes_dir(self):
        src = os.path.join(self.tmp.name, "evil.json")
        with open(src, "w") as f:
            json.dump({"notebooks": [{"notebook": "../../outside", "notes": [
                {"title": "Pwn", "content": "x"}]}]}, f)
        self.assertTrue(self.fm.import_project_from_json(src))
        outside = [p for p in self.all_md() if not p.startswith("notes" + os.sep)]
        self.assertEqual(outside, [])
        self.assertTrue(os.path.exists(os.path.join(self.notes, "outside", "Pwn.md")))

    def test_project_json_round_trip(self):
        self.write("Work/A.md", "---\ntags: [x]\n---\n# A\n\nalpha\n")
        self.assertTrue(self.fm.export_project_to_json(self.out))
        data = json.load(open(self.out))
        self.assertEqual(data["version"], 1)
        titles = {n["title"]: n["notebook"] for n in data["notes"]}
        self.assertEqual(titles["A"], "Work")

    def test_brief_export_then_reimport_overwrites_not_duplicates(self):
        self.write("Home/Shopping.md", "---\ntags: [errands]\n---\n# Shopping\n\nMilk\n")
        self.assertTrue(self.fm.export_to_brief(self.out))
        payload = json.load(open(self.out))
        self.assertEqual(payload["app"], "brief")
        shop = next(n for n in payload["notes"] if n["title"] == "Shopping")
        self.assertIn("notebook:Home", shop["labels"])

        # Simulate an edit made in Brief, then import into an empty workspace
        shop["body"] = "Milk\nEggs"
        os.remove(os.path.join(self.notes, "Home", "Shopping.md"))
        with open(self.out, "w") as f:
            json.dump(payload, f)
        self.assertTrue(self.fm.import_project_from_json(self.out))
        self.assertTrue(self.fm.import_project_from_json(self.out))  # second import: no dupes

        home = [p for p in os.listdir(os.path.join(self.notes, "Home")) if p.endswith(".md")]
        self.assertEqual(home, ["Shopping.md"])
        text = open(os.path.join(self.notes, "Home", "Shopping.md")).read()
        self.assertIn("Eggs", text)
        self.assertIn(f"brief_id: {shop['id']}", text)
        self.assertIn("tags: [errands]", text)

    def test_single_note_brief_export(self):
        path = self.write("Work/Plan.md", "---\ntags: [q4]\n---\n# Plan\n\nBody\n")
        self.assertTrue(self.fm.export_to_brief(self.out, paths=[path]))
        with open(self.out) as f:
            payload = json.load(f)
        self.assertEqual(payload["app"], "brief")
        self.assertEqual([n["title"] for n in payload["notes"]], ["Plan"])

    def test_single_note_json_button_accepts_brief_file(self):
        src = os.path.join(self.tmp.name, "brief.json")
        with open(src, "w") as f:
            json.dump({"app": "brief", "schemaVersion": 1, "exportedAt": "2026-01-01T00:00:00Z",
                       "notes": [{"id": "n1", "type": "text", "title": "From Brief", "body": "hi",
                                  "items": [], "labels": [], "color": "", "pinned": False,
                                  "createdAt": "2026-01-01T00:00:00Z",
                                  "updatedAt": "2026-01-01T00:00:00Z"}]}, f)
        self.assertTrue(self.fm.import_note_from_json(src, None))
        text = open(os.path.join(self.notes, "From Brief.md")).read()
        self.assertIn("# From Brief\n\nhi\n", text)


if __name__ == "__main__":
    unittest.main()
