import base64
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from document_io import read_html,write_html

PNG=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jXioAAAAASUVORK5CYII=")


class DocumentIO(unittest.TestCase):
    def test_embeds_relative_images_and_saves_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);(folder/"image.png").write_bytes(PNG)
            source=folder/"source.html"
            source.write_text('<p>Café — Ελληνικά<img src="image.png" alt="test"></p>',encoding="utf-8")
            doc=read_html(source)
            self.assertEqual(doc["omitted"],0);self.assertIn("data:image/png;base64,",doc["html"])
            destination=folder/"saved.html";write_html(destination,doc["html"])
            (folder/"image.png").unlink()
            self.assertEqual(read_html(destination)["html"],doc["html"])

    def test_remote_and_outside_tree_images_are_not_read(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/"source.html"
            source.write_text('<p><img src="https://example.org/image.png"><img src="../private.png"></p>')
            doc=read_html(source)
            self.assertEqual(doc["omitted"],2);self.assertNotIn("https://",doc["html"])

    def test_unsupported_formats_and_failed_save(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/"original.html";source.write_text("Original")
            with self.assertRaises(ValueError):read_html(folder/"test.odt")
            with self.assertRaises(OSError):write_html(folder/"missing"/"output.html","Changed")
            self.assertEqual(source.read_text(),"Original")


if __name__=="__main__":unittest.main()
