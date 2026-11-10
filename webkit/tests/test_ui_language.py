import locale,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ui_language import use_english_ui

class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.messages=locale.setlocale(locale.LC_MESSAGES)
        self.numeric=locale.setlocale(locale.LC_NUMERIC)
        self.time=locale.setlocale(locale.LC_TIME)

    def tearDown(self):locale.setlocale(locale.LC_MESSAGES,self.messages)

    def test_lc_all_is_preserved_for_formats_but_not_ui_messages(self):
        with patch.dict(os.environ,{'LC_ALL':'nl_NL.UTF-8','LANGUAGE':'nl','LC_TIME':'de_DE.UTF-8'}):
            use_english_ui()
            self.assertNotIn('LC_ALL',os.environ)
            self.assertEqual(os.environ['LANGUAGE'],'en')
            self.assertEqual(os.environ['LC_MESSAGES'],'C')
            for category in ('LC_TIME','LC_NUMERIC','LC_MONETARY','LC_CTYPE','LC_PAPER'):
                self.assertEqual(os.environ[category],'nl_NL.UTF-8')
            self.assertEqual(locale.setlocale(locale.LC_MESSAGES),'C')
            self.assertEqual(locale.setlocale(locale.LC_NUMERIC),self.numeric)
            self.assertEqual(locale.setlocale(locale.LC_TIME),self.time)

    def test_individual_regional_preferences_remain_intact(self):
        with patch.dict(os.environ,{'LANG':'nl_NL.UTF-8','LC_TIME':'de_DE.UTF-8','LC_NUMERIC':'nl_NL.UTF-8'},clear=True):
            use_english_ui()
            self.assertEqual(os.environ['LANG'],'nl_NL.UTF-8')
            self.assertEqual(os.environ['LC_TIME'],'de_DE.UTF-8')
            self.assertEqual(os.environ['LC_NUMERIC'],'nl_NL.UTF-8')
            self.assertEqual(os.environ['LANGUAGE'],'en')
