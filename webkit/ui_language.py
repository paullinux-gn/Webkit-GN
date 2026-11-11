"""Follow the desktop locale without overriding language or regional settings."""
import locale


def use_desktop_language():
    # Honour LANGUAGE, LC_ALL, LC_MESSAGES and LANG using the standard locale
    # precedence. GTK/WebKit inherit these same settings in their subprocesses.
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        # A host may name a locale absent from the runtime. Keep the current
        # locale and let the toolkit fall back without preventing app startup.
        pass
