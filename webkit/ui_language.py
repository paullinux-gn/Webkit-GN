"""Use English UI messages without changing regional document formatting."""
import locale
import os


def use_english_ui():
    # LC_ALL would override LC_MESSAGES in GTK and spawned WebKit helpers.
    # Preserve its effective regional settings as individual categories instead.
    inherited=os.environ.pop('LC_ALL',None)
    if inherited:
        for category in ('LC_CTYPE','LC_NUMERIC','LC_TIME','LC_COLLATE','LC_MONETARY',
                         'LC_PAPER','LC_NAME','LC_ADDRESS','LC_TELEPHONE',
                         'LC_MEASUREMENT','LC_IDENTIFICATION'):
            os.environ[category]=inherited
    os.environ['LANGUAGE']='en'
    os.environ['LC_MESSAGES']='C'
    # Also cover an interpreter whose message locale was already initialised.
    locale.setlocale(locale.LC_MESSAGES,'C')
