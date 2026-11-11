import locale
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_language import use_desktop_language


class LanguageTests(unittest.TestCase):
    def test_desktop_language_and_regional_overrides_are_preserved(self):
        preferences = {'LANG': 'nl_BE.UTF-8', 'LANGUAGE': 'nl:en',
                       'LC_MESSAGES': 'nl_NL.UTF-8', 'LC_TIME': 'de_DE.UTF-8',
                       'LC_ALL': 'nl_BE.UTF-8'}
        with patch.dict(os.environ, preferences, clear=True):
            with patch('ui_language.locale.setlocale') as apply:
                use_desktop_language()
                apply.assert_called_once_with(locale.LC_ALL, '')
            self.assertEqual(dict(os.environ), preferences)

    def test_missing_locale_does_not_block_startup_or_change_environment(self):
        preferences = {'LANG': 'unavailable.UTF-8', 'LANGUAGE': 'nl:en'}
        with patch.dict(os.environ, preferences, clear=True):
            with patch('ui_language.locale.setlocale', side_effect=locale.Error):
                use_desktop_language()
            self.assertEqual(dict(os.environ), preferences)

    def test_no_language_override_is_invented(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch('ui_language.locale.setlocale'):
                use_desktop_language()
            self.assertEqual(dict(os.environ), {})
