"""Actual PDF preview navigation and settings regeneration in the native dialog."""
from pathlib import Path
import sys,os,time,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'webkit'))
prefs=tempfile.TemporaryDirectory();os.environ['GNOME_WP_SETTINGS_FILE']=str(Path(prefs.name)/'interface.json')
from app import App,GLib,Gtk
app=App();app.register(None);app.activate();window=app.get_active_window();context=GLib.MainContext.default()
errors=[]
sys.excepthook=lambda kind,error,tb:errors.append(str(error))
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
    folder=ROOT/'.runtime/line-spacing';folder.mkdir(parents=True,exist_ok=True)
    js('window.editor.loadHTML("<p>First paragraph with enough text to wrap across several lines. First paragraph with enough text to wrap across several lines. First paragraph with enough text to wrap across several lines.</p><p>Second paragraph stays unchanged.</p>")')
    js('window.editor.select(1)');pump()
    window.line_spacing_menu.popup();pump(minimum=.2)
    subprocess.run(['import','-window','root',str(folder/'dropdown.png')],check=True)
    window.line_spacing_buttons[2].set_active(True);pump(lambda:window.state['format']['lineSpacing']==2)
    values=js('Array.from(document.querySelectorAll(".ProseMirror > p"),p=>getComputedStyle(p).lineHeight)')
    assert values==['32px','24px'],values
    js('window.editor.select(window.editor.view.state.doc.firstChild.nodeSize+1)');pump()
    assert window.line_spacing_buttons[1.5].get_active()
    js('window.editor.select(1,window.editor.view.state.doc.content.size-1)')
    window.line_spacing_buttons[1.15].set_active(True);pump(lambda:window.state['format']['lineSpacing']==1.15)
    values=js('Array.from(document.querySelectorAll(".ProseMirror > p"),p=>parseFloat(getComputedStyle(p).lineHeight))')
    assert all(abs(value-18.4)<.1 for value in values),values
    before=js('window.editor.getState()')['json'];exported=js('window.editor.exportHTML()')['html']
    import json
    js('window.editor.loadHTML('+json.dumps(exported)+')')
    assert js('window.editor.getState()')['json']==before
    print('PASS: native line-spacing dropdown, actual rendered single/multiple paragraph spacing, current-setting indicator and HTML round trip',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
