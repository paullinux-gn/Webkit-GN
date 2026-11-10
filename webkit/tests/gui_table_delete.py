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
    from toolbar import table_dialog
    js('window.editor.loadHTML("<p>Before</p><table><tr><td><p>Cell</p></td></tr></table><p>After</p>")')
    original=js('window.editor.getState()')['json']
    info=js('window.editor.getTable(window.editor.view.state.doc.firstChild.nodeSize)')
    table_dialog(window,info);pump(lambda:window.table_window.get_mapped())
    assert window.table_delete_button.get_label()=='Delete table'
    window.table_delete_button.emit('clicked');pump(lambda:window.table_window is None)
    pump(lambda:js('window.editor.view.dom.querySelector("table")===null'))
    assert js('window.editor.getText()')=='Before\nAfter'
    window.command('undo');pump(lambda:js('window.editor.getState()')['json']==original)
    print('PASS: native table menu deletes selected table, preserves nearby text and supports undo',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
