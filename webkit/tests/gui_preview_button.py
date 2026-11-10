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
    js('window.editor.loadHTML("<p>Dedicated print preview button.</p>")')
    window.preview_button.emit('clicked')
    pump(lambda:window.print_dialog is not None and window.print_preview.box.get_mapped())
    pump(lambda:window.print_preview.pages>0 and not window.print_preview.busy)
    assert window.print_preview.picture.get_paintable() is not None
    assert window.preview_button.get_child().get_gicon().get_names()[0]=='document-print-preview-symbolic'
    window.print_dialog.response(Gtk.ResponseType.CANCEL);pump()
    window.file_actions['print'].activate(None);pump(lambda:window.print_dialog is not None)
    dialog=window.print_dialog
    assert not window.print_preview.box.get_mapped()
    window.file_actions['print-preview'].activate(None)
    pump(lambda:window.print_preview.box.get_mapped())
    assert window.print_dialog is dialog
    pump(lambda:window.print_preview.pages>0 and not window.print_preview.busy)
    window.print_dialog.response(Gtk.ResponseType.CANCEL);pump()
    assert not js('window.editor.getSummary()')['dirty']
    assert app.get_accels_for_action('win.print-preview')
    print('PASS: separate native preview icon opens and renders Preview directly; Print keeps its usual tab; menu/shortcut action reuses the existing dialog; document unchanged',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
