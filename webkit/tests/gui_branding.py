"""Actual PDF preview navigation and settings regeneration in the native dialog."""
from pathlib import Path
import sys,os,time,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'webkit'))
prefs=tempfile.TemporaryDirectory();os.environ['GNOME_WP_SETTINGS_FILE']=str(Path(prefs.name)/'interface.json')
from app import App,GLib,Gtk,WebKit
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
    app_id='io.github.paullinux_gn.WebkitGN'
    assert app.get_application_id()==app_id
    assert window.get_title()=='Webkit-GN'
    assert window.get_icon_name()==app_id
    theme=Gtk.IconTheme.get_for_display(window.get_display())
    assert theme.has_icon(app_id)
    print('PASS: Webkit-GN application ID, window title and bundled GNOME document icon',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
