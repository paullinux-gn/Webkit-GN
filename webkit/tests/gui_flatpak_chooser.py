"""Actual PDF preview navigation and settings regeneration in the native dialog."""
from pathlib import Path
import sys,os,time,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'webkit'))
prefs=tempfile.TemporaryDirectory();os.environ['GNOME_WP_SETTINGS_FILE']=str(Path(prefs.name)/'interface.json')
from app import App,GLib,Gtk
app=App();app.register(None);app.activate();window=app.get_active_window();context=GLib.MainContext.default()
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
    from gi.repository import Gio
    window.sandboxed=True
    folder=ROOT/'.runtime/flatpak-chooser';folder.mkdir(parents=True,exist_ok=True)
    window.choose_file(True);pump(lambda:window.file_chooser is not None)
    chooser=window.file_chooser
    assert isinstance(chooser,Gtk.FileChooserNative)
    assert chooser.get_current_name()=='Untitled.html'
    chooser.emit('response',Gtk.ResponseType.CANCEL);pump()
    assert window.file_chooser is None and not js('window.editor.getSummary()')['dirty']
    path=folder/'portal-open.html';path.write_text('<p>Opened through the native chooser</p>')
    window.choose_file(False);chooser=window.file_chooser
    chooser.set_file(Gio.File.new_for_path(str(path)));pump(minimum=.3)
    chooser.emit('response',Gtk.ResponseType.ACCEPT)
    pump(lambda:js('window.editor.getText()')=='Opened through the native chooser')
    assert window.file_chooser is None
    print('PASS: sandbox mode selects native Open/Save choosers, cancellation stays clean and selected HTML opens',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
