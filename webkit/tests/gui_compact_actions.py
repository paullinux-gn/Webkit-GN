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
    folder=ROOT/'.runtime/compact-actions';folder.mkdir(parents=True,exist_ok=True)
    js('window.editor.loadHTML("<p>Right-click this document text.</p>")')
    import ctypes as C
    x11=C.CDLL('libX11.so.6');xtest=C.CDLL('libXtst.so.6')
    x11.XOpenDisplay.argtypes=[C.c_char_p];x11.XOpenDisplay.restype=C.c_void_p
    x11.XFlush.argtypes=[C.c_void_p];x11.XCloseDisplay.argtypes=[C.c_void_p]
    xtest.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
    xtest.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    display=x11.XOpenDisplay(None);assert display
    def descendants(widget):
        yield widget;child=widget.get_first_child()
        while child:yield from descendants(child);child=child.get_next_sibling()
    for theme,expected in (('light',(32,33,36)),('mixed',(242,243,245)),('dark',(242,243,245))):
        window.change_appearance(theme=theme);pump()
        window.menu_button.popup();pump()
        hamburger=window.menu_button.get_popover()
        assert hamburger.has_css_class('compact-action-menu')
        rows=[w for w in descendants(hamburger) if w.get_css_name()=='modelbutton' and w.get_mapped()]
        assert rows and all(w.get_height()<=34 for w in rows),[(w.get_height(),type(w).__name__) for w in rows]
        subprocess.run(['import','-window','root',str(folder/(theme+'-hamburger.png'))],check=True)
        window.menu_button.popdown();pump()
        xtest.XTestFakeMotionEvent(display,-1,220,295,0)
        xtest.XTestFakeButtonEvent(display,3,True,0);xtest.XTestFakeButtonEvent(display,3,False,0);x11.XFlush(display)
        found=[]
        def visible_menu():
            found[:]=[w for w in descendants(window.webview) if isinstance(w,Gtk.Popover) and w.get_mapped()]
            return bool(found)
        pump(visible_menu)
        assert found[0].has_css_class('compact-action-menu'),type(found[0]).__name__
        rows=[w for w in descendants(found[0]) if w.get_css_name()=='modelbutton' and w.get_mapped()]
        assert rows and all(w.get_height()<=34 for w in rows),[(w.get_height(),type(w).__name__) for w in rows]
        content=next(w for w in descendants(found[0]) if w.get_css_name()=='contents')
        c=content.get_color();actual=tuple(round(v*255) for v in (c.red,c.green,c.blue))
        assert actual==expected,(theme,actual)
        subprocess.run(['import','-window','root',str(folder/(theme+'.png'))],check=True)
        found[0].popdown();pump()
    x11.XCloseDisplay(display)
    print('PASS: hamburger and actual right-click menus have compact rows and follow all three themes',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
