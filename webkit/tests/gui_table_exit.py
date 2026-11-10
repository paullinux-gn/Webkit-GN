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
    js('window.editor.loadHTML("<table data-floating=true><tr><td><p>Existing table text</p></td></tr></table>")')
    js('window.editor.select(4)');pump(lambda:bool(window.state.get('table')))
    window.action_buttons['table'].emit('clicked');pump(lambda:window.table_window is not None)
    window.table_exit_button.emit('clicked');pump(lambda:window.table_window is None and not window.state.get('table'))
    window.command('insertText',{'text':'Typed outside the table'});pump()
    data=js('window.editor.getState()')['json']
    assert data['content'][0]['type']=='table' and data['content'][0]['content'][0]['content'][0]['content'][0]['content'][0]['text']=='Existing table text'
    assert data['content'][1]['attrs']['clear']
    assert data['content'][1]['content'][0]['text']=='Typed outside the table'
    layout=js('({table:document.querySelector("table").getBoundingClientRect().bottom,paragraph:document.querySelector(".ProseMirror > p").getBoundingClientRect().top})')
    assert layout['paragraph']>=layout['table'],layout
    js('window.editor.select(4)');pump(lambda:bool(window.state.get('table')))
    # A real Alt+Enter must reach WebKit, not be consumed by GTK.
    import ctypes as C
    x11=C.CDLL('libX11.so.6');xtest=C.CDLL('libXtst.so.6')
    x11.XOpenDisplay.argtypes=[C.c_char_p];x11.XOpenDisplay.restype=C.c_void_p
    x11.XStringToKeysym.argtypes=[C.c_char_p];x11.XStringToKeysym.restype=C.c_ulong
    x11.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x11.XKeysymToKeycode.restype=C.c_uint
    x11.XFlush.argtypes=[C.c_void_p];x11.XCloseDisplay.argtypes=[C.c_void_p]
    xtest.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    display=x11.XOpenDisplay(None);assert display
    window.webview.grab_focus();pump()
    def key(name,pressed):
        code=x11.XKeysymToKeycode(display,x11.XStringToKeysym(name.encode()))
        xtest.XTestFakeKeyEvent(display,code,pressed,0)
    key('Alt_L',True);key('Return',True);key('Return',False);key('Alt_L',False);x11.XFlush(display)
    pump(lambda:not window.state.get('table'))
    assert js('window.editor.view.state.doc.childCount')==2
    x11.XCloseDisplay(display)
    print('PASS: table-menu exit creates a paragraph below floating table, preserves cells, allows typing outside, and real Alt+Enter reuses the paragraph',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
