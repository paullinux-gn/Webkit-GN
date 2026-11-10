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
    folder=ROOT/'.runtime/search-pill';folder.mkdir(parents=True,exist_ok=True)
    js('window.editor.loadHTML("<p>Alpha alpha beta Alpha.</p>")')
    window.find_button.emit('clicked');pump(lambda:window.search.widget.get_visible())
    pill=window.search;pill.query.set_text('alpha');pump(lambda:pill.counter.get_text()=='1/3')
    assert not js('window.editor.getSummary()')['dirty']
    focus=window.get_focus();assert focus is pill.query or focus.is_ancestor(pill.query)
    assert window.find_button.is_ancestor(window.toolbar_rows[0])
    for theme in ('light','dark','mixed'):
        window.change_appearance(theme=theme,blur=True);pump(minimum=.2)
        ok,bar=window.tools.compute_bounds(window);assert ok
        ok,search=pill.widget.compute_bounds(window);assert ok
        assert abs(search.get_x()+search.get_width()/2-window.get_width()/2)<1
        assert 6<=search.get_y()-bar.get_y()-bar.get_height()<=10
        assert pill.widget.get_color().to_string()==window.tools.get_color().to_string()
        if not window.native_blur:
            assert js('getComputedStyle(document.getElementById("search-glass")).display')=='block'
            assert 'blur(' in js('getComputedStyle(document.getElementById("search-glass")).backdropFilter')
        subprocess.run(['import','-window','root',str(folder/(theme+'.png'))],check=True)
    pill.case.set_active(True);pump(lambda:pill.counter.get_text().endswith('/1'))
    js('window.editor.select(1)');pill.case.set_active(False);pump(lambda:pill.counter.get_text()=='1/3')
    pill.previous.emit('clicked');pump(lambda:pill.counter.get_text()=='3/3')
    pill.next.emit('clicked');pump(lambda:pill.counter.get_text()=='1/3')
    pill.replacement.set_text('Omega');pill.replace.emit('clicked');pump(lambda:js('window.editor.getText()')=='Omega alpha beta Alpha.')
    pill.replace_all.emit('clicked');pump(lambda:js('window.editor.getText()')=='Omega Omega beta Omega.')
    window.command('undo');pump(lambda:js('window.editor.getText()')=='Omega alpha beta Alpha.')
    pill.close.emit('clicked');pump(lambda:not pill.widget.get_visible())
    assert not window.find_button.get_active()
    assert js('document.querySelector(".search-match")') is None
    window.file_actions['find-replace'].activate(None);pump(lambda:pill.widget.get_visible())
    pump(lambda:pill.counter.get_text().endswith('/2'))
    from gi.repository import Gio
    menu=window.menu_button.get_menu_model();items=[]
    for i in range(menu.get_n_items()):
        section=menu.get_item_link(i,Gio.MENU_LINK_SECTION)
        if section:
            for j in range(section.get_n_items()):
                label=section.get_item_attribute_value(j,Gio.MENU_ATTRIBUTE_LABEL,None)
                if label and label.get_string()=='Search and replace…':
                    assert section.get_item_link(j,Gio.MENU_LINK_SUBMENU) is None;items.append(True)
    assert len(items)==1
    pill.close.emit('clicked');pump()
    import ctypes as C
    x11=C.CDLL('libX11.so.6');xtest=C.CDLL('libXtst.so.6')
    x11.XOpenDisplay.argtypes=[C.c_char_p];x11.XOpenDisplay.restype=C.c_void_p
    x11.XStringToKeysym.argtypes=[C.c_char_p];x11.XStringToKeysym.restype=C.c_ulong
    x11.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x11.XKeysymToKeycode.restype=C.c_uint
    x11.XFlush.argtypes=[C.c_void_p];x11.XCloseDisplay.argtypes=[C.c_void_p]
    xtest.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    display=x11.XOpenDisplay(None);assert display
    def key(symbol,down):
        code=x11.XKeysymToKeycode(display,x11.XStringToKeysym(symbol.encode()))
        xtest.XTestFakeKeyEvent(display,code,down,0)
    window.webview.grab_focus();pump()
    key('Control_L',True);key('h',True);key('h',False);key('Control_L',False);x11.XFlush(display)
    pump(lambda:pill.widget.get_visible())
    key('Escape',True);key('Escape',False);x11.XFlush(display)
    pump(lambda:not pill.widget.get_visible())
    assert window.webview.has_focus()
    x11.XCloseDisplay(display)
    print('PASS: top-row search icon, one direct menu item, centred floating pill in all themes with blur, focus retention, navigation, case matching, replace/all and undo',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
