from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from appearance import AppearanceStore,DEFAULTS,normalise


class AppearanceTests(unittest.TestCase):
    def test_missing_and_malformed_preferences_use_mixed_theme(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"interface.json";store=AppearanceStore(path)
            self.assertEqual(store.load(),DEFAULTS)
            self.assertEqual(store.load()["theme"],"mixed")
            self.assertFalse(store.load()["blur"])
            path.write_text("invalid JSON")
            self.assertEqual(store.load(),DEFAULTS)

    def test_preferences_survive_restarting_the_store(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"settings"/"interface.json"
            selected={"theme":"dark","blur":True,"opacity":0.65,"blur_radius":22}
            AppearanceStore(path).save(selected)
            self.assertEqual(AppearanceStore(path).load(),selected)

    def test_invalid_values_cannot_generate_invalid_css(self):
        result=normalise({"theme":"unknown","blur":"true","opacity":5,"blur_radius":float("nan")})
        self.assertEqual(result,{**DEFAULTS,"opacity":1.0})

    def test_non_blur_menu_surfaces_are_opaque_even_at_low_opacity(self):
        from ui_surfaces import surface_css
        for dark in (False,True):
            for native in (False,True):
                css=surface_css(dark,0.2,native,14,False)
                rgb="37,39,45" if dark else "250,250,252"
                self.assertIn(f"@define-color wp_surface rgba({rgb},1);",css)
                self.assertNotIn("backdrop-filter:",css)

    def test_legacy_light_preferences_migrate_once_then_respect_user_choice(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"interface.json"
            path.write_text(json.dumps({"theme":"light","blur":True,"opacity":0.6}))
            store=AppearanceStore(path)
            migrated=store.load()
            self.assertEqual(migrated["theme"],"mixed")
            self.assertFalse(migrated["blur"])
            self.assertEqual(migrated["opacity"],0.6)
            store.save({**migrated,"theme":"light","blur":True})
            self.assertEqual(store.load()["theme"],"light")
            self.assertTrue(store.load()["blur"])
