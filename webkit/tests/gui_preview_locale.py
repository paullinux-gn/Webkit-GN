"""Actual PDF preview navigation and settings regeneration in the native dialog."""
from pathlib import Path
import sys,os,time,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'webkit'))
prefs=tempfile.TemporaryDirectory();os.environ['GNOME_WP_SETTINGS_FILE']=str(Path(prefs.name)/'interface.json')
import locale
os.environ['LANGUAGE']='nl'
os.environ['LC_ALL']='nl_NL.UTF-8'
locale.setlocale(locale.LC_ALL,'nl_NL.UTF-8')
from app import App,GLib,Gtk
# Rootless cloud GTK locales live beside the extracted library rather than in
# the system directory. Desktop installations already use their system locale.
locale_dir=Path('/workspace/toolchains/gtk/usr/share/locale')
if locale_dir.exists():locale.bindtextdomain('gtk40',str(locale_dir))
app=App();app.register(None);
if locale_dir.exists():locale.bindtextdomain("gtk40",str(locale_dir))
app.activate();window=app.get_active_window();context=GLib.MainContext.default()
errors=[]
sys.excepthook=lambda kind,error,tb:(errors.append(str(error)),sys.__excepthook__(kind,error,tb))
def pump(predicate=lambda:True,minimum=.1):
    start=time.monotonic()
    while time.monotonic()-start<minimum or not predicate():
        assert time.monotonic()-start<60,(errors,getattr(getattr(window,'print_preview',None),'label',window.status).get_text())
        for _ in range(100):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.003)
    assert not errors,errors

def js(text):
    result=[];window.js(text,result.append);pump(lambda:bool(result));return result[0]
try:
    pump(lambda:window.state.get('ready'))
    printers=[]
    def discovered(printer,*_):
        if printer.is_virtual() and printer.accepts_pdf():printers.append(printer);return True
        return False
    Gtk.enumerate_printers(discovered,None,False);pump(lambda:bool(printers))
    name=printers[0].get_name();assert name=='Afdrukken naar bestand',name
    print('Confirmed Dutch virtual PDF printer: '+name,flush=True)
    output=ROOT/'.runtime/preview-locale';output.mkdir(parents=True,exist_ok=True)
    legacy=window.create_print_operation();settings=Gtk.PrintSettings();settings.set_printer('Print to File')
    settings.set('output-uri',(output/'legacy.pdf').as_uri());settings.set('output-file-format','pdf')
    legacy.set_print_settings(settings);failed=[];finished=[]
    legacy.connect('failed',lambda _,error:failed.append(error.message));legacy.connect('finished',lambda _:finished.append(True))
    legacy.print_();pump(lambda:bool(failed or finished));assert failed,'Old English printer name unexpectedly worked'
    print('Reproduced original failure: '+failed[0],flush=True)
    js('window.editor.loadHTML("<p>Preview without a physical printer.</p>")')
    window.print_document();pump(lambda:window.print_dialog is not None)
    preview=window.print_preview;preview.generate();pump(lambda:preview.pages>0 and not preview.busy)
    assert preview.pdf.read_bytes().startswith(b'%PDF-') and preview.picture.get_paintable() is not None
    assert not preview.label.get_text().startswith('Preview failed'),preview.label.get_text()
    window.print_dialog.response(Gtk.ResponseType.CANCEL);pump()
    assert not js('window.editor.getSummary()')['dirty']
    # Closing while printer discovery is pending must release the worker safely.
    original=Gtk.enumerate_printers
    Gtk.enumerate_printers=lambda *args:None
    try:
        window.print_document();preview=window.print_preview;preview.generate()
        assert preview.searching
        pump(lambda:not preview.busy)
        assert 'backend is missing or disabled' in preview.label.get_text()
        assert preview.refresh.get_sensitive()
        window.print_dialog.response(Gtk.ResponseType.CANCEL);pump()
        assert preview.closed and not preview.discovery_timer
        window.print_document();preview=window.print_preview;preview.generate()
        window.print_dialog.response(Gtk.ResponseType.CANCEL);pump()
        assert preview.closed and not preview.discovery_timer
    finally:Gtk.enumerate_printers=original
    print('PASS: Dutch PDF preview, physical-printer independence, PDF rendering, clean document and closing during discovery',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
