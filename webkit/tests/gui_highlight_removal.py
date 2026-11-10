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
    js('window.editor.loadHTML("<p>Normal colour after highlighting</p>")');js('window.editor.select(1,32)')
    window.command('highlight',{'value':'#1a5fb4'});pump()
    js('window.editor.select(10)');window.webview.grab_focus();pump()
    import ctypes as C
    x11=C.CDLL('libX11.so.6');xtest=C.CDLL('libXtst.so.6')
    x11.XOpenDisplay.argtypes=[C.c_char_p];x11.XOpenDisplay.restype=C.c_void_p
    x11.XStringToKeysym.argtypes=[C.c_char_p];x11.XStringToKeysym.restype=C.c_ulong
    x11.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x11.XKeysymToKeycode.restype=C.c_uint
    x11.XFlush.argtypes=[C.c_void_p];x11.XCloseDisplay.argtypes=[C.c_void_p]
    xtest.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    display=x11.XOpenDisplay(None);assert display
    code=x11.XKeysymToKeycode(display,x11.XStringToKeysym(b'x'))
    xtest.XTestFakeKeyEvent(display,code,True,0);xtest.XTestFakeKeyEvent(display,code,False,0);x11.XFlush(display)
    pump(lambda:'x' in js('window.editor.getText()'))
    js('window.editor.select(1,window.editor.view.state.doc.content.size-1)')
    window.palette_buttons['highlight'][None].emit('clicked');pump()
    marks=js('window.editor.getState()')['json']['content'][0]['content'][0].get('marks',[])
    assert not any(m['type'] in ('color','highlight') for m in marks),marks
    assert js('getComputedStyle(document.querySelector(".ProseMirror p")).color')=='rgb(32, 33, 36)'
    # Simulate saved content affected by an older version's white-colour leak.
    import json
    affected='<p><span style="color:white"><span data-highlight="true" data-auto-contrast="true" data-highlight-colour="#1a5fb4" style="background-color:#1a5fb4;color:white">Affected saved text</span></span></p>'
    js('window.editor.loadHTML('+json.dumps(affected)+')');js('window.editor.select(1,window.editor.view.state.doc.content.size-1)')
    window.palette_buttons['highlight'][None].emit('clicked');pump()
    assert not js('window.editor.getState()')['json']['content'][0]['content'][0].get('marks')
    x11.XCloseDisplay(display)
    print('PASS: real WebKit typing inside a dark highlight, removal restores normal dark text, and old saved automatic-white leaks are repaired',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
