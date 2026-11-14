import unittest

from notes_app import note_format as nf


class FrontMatterTests(unittest.TestCase):
    def test_parse_tags_handles_quotes_and_commas(self):
        self.assertEqual(nf.parse_tags_value('[a, "b, c", \'d\']'), ["a", "b, c", "d"])
        self.assertEqual(nf.parse_tags_value("[]"), [])
        self.assertEqual(nf.parse_tags_value("work, ideas"), ["work", "ideas"])

    def test_format_tags_round_trips(self):
        tags = ["work", "a, b", "x[y]"]
        line = nf.format_tags_line(tags)
        self.assertEqual(nf.parse_tags_value(line.split(":", 1)[1]), ["work", "a, b", "xy"])

    def test_parse_front_matter_extra_keys(self):
        meta = nf.parse_front_matter("---\ntags: [a]\npinned: true\ncolor: blue\nbrief_id: abc\n---\n")
        self.assertEqual(meta["tags"], ["a"])
        self.assertTrue(meta["pinned"])
        self.assertEqual(meta["color"], "blue")
        self.assertEqual(meta["brief_id"], "abc")


class TitleTests(unittest.TestCase):
    def test_title_ignores_code_fences(self):
        body = "```bash\n# not a title\n```\n\n# Real Title\n"
        self.assertEqual(nf.find_title(body), "Real Title")

    def test_hashtag_is_not_heading(self):
        self.assertIsNone(nf.find_title("#todo something\n"))

    def test_strip_title_heading(self):
        self.assertEqual(nf.strip_title_heading("# T\n\nBody\n"), "Body\n")
        self.assertEqual(nf.strip_title_heading("Body only\n# Later\n"), "Body only\n# Later\n")


class SafeNotebookTests(unittest.TestCase):
    def test_traversal_is_neutralised(self):
        self.assertEqual(nf.safe_notebook_name("../../etc"), "etc")
        self.assertIsNone(nf.safe_notebook_name("../.."))
        self.assertIsNone(nf.safe_notebook_name(None))
        self.assertEqual(nf.safe_notebook_name("/abs/path"), "abspath")


class BriefConversionTests(unittest.TestCase):
    RAW = "---\ntags: [work, \"a, b\"]\npinned: true\ncolor: teal\n---\n# Shopping\n\nMilk\n"

    def test_note_to_brief_shape(self):
        n = nf.note_to_brief(self.RAW, "Home/Shopping.md", 1_700_000_000)
        self.assertEqual(n["title"], "Shopping")
        self.assertEqual(n["body"], "Milk")
        self.assertEqual(n["labels"], ["work", "a, b", "notebook:Home"])
        self.assertEqual(n["type"], "text")
        self.assertEqual(n["items"], [])
        self.assertEqual(n["color"], "teal")
        self.assertTrue(n["pinned"])
        self.assertNotIn("/", n["id"])
        self.assertEqual(n["updatedAt"], "2023-11-14T22:13:20Z")
        # Stable across exports
        self.assertEqual(n["id"], nf.note_to_brief(self.RAW, "Home/Shopping.md", 1)["id"])

    def test_payload_passes_brief_validation_rules(self):
        payload = nf.make_brief_payload([nf.note_to_brief(self.RAW, "x.md", 0)], 0)
        self.assertEqual(payload["app"], "brief")
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(len(nf.validate_brief_payload(payload)), 1)
        # Every field Brief's validateNote() requires, with the right type
        n = payload["notes"][0]
        for key, typ in [("id", str), ("type", str), ("title", str), ("body", str), ("items", list),
                         ("labels", list), ("color", str), ("pinned", bool), ("createdAt", str),
                         ("updatedAt", str)]:
            self.assertIsInstance(n[key], typ, key)

    def test_brief_round_trip(self):
        n = nf.note_to_brief(self.RAW, "Home/Shopping.md", 1_700_000_000)
        nb, title, text, ts = nf.brief_to_note(n)
        self.assertEqual(nb, "Home")
        self.assertEqual(title, "Shopping")
        self.assertEqual(ts, 1_700_000_000)
        back = nf.parse_note(text, "x")
        self.assertEqual(back["title"], "Shopping")
        self.assertEqual(back["meta"]["tags"], ["work", "a, b"])
        self.assertTrue(back["meta"]["pinned"])
        self.assertEqual(back["meta"]["brief_id"], n["id"])
        self.assertEqual(back["meta"]["color"], "teal")

    def test_list_note_becomes_bullets(self):
        nb, title, text, _ = nf.brief_to_note({
            "id": "abc", "type": "list", "title": "", "body": "",
            "items": [{"id": "1", "text": "Eggs"}, {"id": "2", "text": "Bread"}],
            "labels": ["notebook:../../evil"], "color": "", "pinned": False,
            "createdAt": "2025-01-01T00:00:00.000Z", "updatedAt": "2025-01-02T00:00:00.000Z",
        })
        self.assertEqual(nb, "evil")
        self.assertEqual(title, "Untitled")
        self.assertIn("- Eggs\n- Bread\n", text)

    def test_validation_rejects_bad_envelope_and_skips_bad_notes(self):
        with self.assertRaises(ValueError):
            nf.validate_brief_payload({"app": "brief", "schemaVersion": 2, "notes": []})
        notes = nf.validate_brief_payload({"app": "brief", "schemaVersion": 1, "notes": [
            {"id": "a/b", "type": "text"}, {"id": "ok", "type": "text"}, {"id": "x", "type": "video"}]})
        self.assertEqual([n["id"] for n in notes], ["ok"])


if __name__ == "__main__":
    unittest.main()
