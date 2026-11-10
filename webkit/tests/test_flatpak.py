"""Packaging metadata consistency and document-portal file semantics."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'webkit'))
from document_io import write_html

class FlatpakTests(unittest.TestCase):
    def test_ids_and_required_runtime_assets_agree(self):
        manifest=json.loads((ROOT/'flatpak/io.github.paullinux_gn.WebkitGN.json').read_text())
        app_id=manifest['app-id']
        metadata=ET.parse(ROOT/'data'/f'{app_id}.metainfo.xml').getroot()
        self.assertEqual(metadata.findtext('id'),app_id)
        self.assertEqual(metadata.findtext('launchable'),app_id+'.desktop')
        desktop=(ROOT/'data'/f'{app_id}.desktop').read_text()
        self.assertIn('Exec='+manifest['command']+'\n',desktop)
        self.assertIn('Icon='+app_id+'\n',desktop)
        self.assertTrue((ROOT/'data/icons/hicolor/scalable/apps'/f'{app_id}.svg').is_file())
        self.assertTrue((ROOT/'flatpak'/manifest['command']).is_file())
        self.assertNotIn('--filesystem=host',manifest['finish-args'])
        self.assertNotIn('--filesystem=home',manifest['finish-args'])
        self.assertNotIn('--share=network',manifest['finish-args'])

    def test_portal_save_needs_no_sibling_file_or_rename(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'doc'/'grant'/'document.html'
            path.parent.mkdir(parents=True);path.write_text('before')
            with patch.dict(os.environ,{'FLATPAK_ID':'io.github.paullinux_gn.WebkitGN','XDG_RUNTIME_DIR':folder}):
                with patch('document_io.tempfile.NamedTemporaryFile',side_effect=PermissionError('No sibling grant')):
                    write_html(path,'<p>Saved via portal</p>')
            self.assertEqual(path.read_text(),'<p>Saved via portal</p>')

    def test_other_paths_still_require_atomic_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'document.html';path.write_text('original')
            with patch.dict(os.environ,{'FLATPAK_ID':'io.github.paullinux_gn.WebkitGN','XDG_RUNTIME_DIR':folder}):
                with patch('document_io.tempfile.NamedTemporaryFile',side_effect=PermissionError('Read only')):
                    with self.assertRaises(PermissionError):write_html(path,'replacement')
            self.assertEqual(path.read_text(),'original')
