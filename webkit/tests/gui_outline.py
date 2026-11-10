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
    import json
    from gi.repository import Gio
    paragraphs='<p>'+('Body text for scrolling. '*12)+'</p>'
    html='<h1 data-style="Title">Outline demo</h1><h1>Chapter one</h1>'+paragraphs*25+'<h2>Details</h2>'+paragraphs*25+'<h3>Final section</h3>'+paragraphs*25
    js('window.editor.loadHTML('+json.dumps(html)+')');pump()
    before=js('window.editor.getState()')
    window.outline_button.emit('clicked');panel=window.outline
    pump(lambda:panel.widget.get_visible() and len(panel.rows)==4)
    assert window.outline_button.get_parent() is window.toolbar_rows[0].get_last_child()
    labels=[row.get_child() for row in panel.rows.values()]
    assert all(int(label.get_pango_context().get_font_description().get_weight())==400 for label in labels)
    folder=ROOT/'.runtime/outline';folder.mkdir(parents=True,exist_ok=True)
    for theme in ('light','dark','mixed'):
        window.change_appearance(theme=theme,blur=True);pump(minimum=.2)
        ok,bar=window.tools.compute_bounds(window);assert ok
        ok,box=panel.widget.compute_bounds(window);assert ok
        ok,button=window.outline_button.compute_bounds(window);assert ok
        assert abs(box.get_x()+box.get_width()/2-window.get_width()/2)<1
        assert 6<=box.get_y()-bar.get_y()-bar.get_height()<=10
        assert 4<=bar.get_x()+bar.get_width()-button.get_x()-button.get_width()<=14,(bar.get_width(),button.get_x(),button.get_width())
        assert panel.widget.get_color().to_string()==window.tools.get_color().to_string()
        if not window.native_blur:assert js('getComputedStyle(document.getElementById("outline-glass")).display')=='block'
        subprocess.run(['import','-window','root',str(folder/(theme+'.png'))],check=True)
    target=panel.data['headings'][-1];row=panel.rows[target['position']]
    # Click a real outline row, including the outside-click capture controller.
    import ctypes as C
    x11=C.CDLL('libX11.so.6');xtest=C.CDLL('libXtst.so.6')
    x11.XOpenDisplay.argtypes=[C.c_char_p];x11.XOpenDisplay.restype=C.c_void_p
    x11.XFlush.argtypes=[C.c_void_p];x11.XCloseDisplay.argtypes=[C.c_void_p]
    xtest.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
    xtest.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    display=x11.XOpenDisplay(None);assert display
    def click(x,y):
        xtest.XTestFakeMotionEvent(display,-1,round(x),round(y),0)
        xtest.XTestFakeButtonEvent(display,1,True,0);xtest.XTestFakeButtonEvent(display,1,False,0);x11.XFlush(display)
    ok,bounds=row.compute_bounds(window);assert ok
    click(bounds.get_x()+bounds.get_width()/2,bounds.get_y()+bounds.get_height()/2)
    pump(lambda:not panel.widget.get_visible())
    assert js('window.editor.view.state.selection.from')==target['position']+1
    top=js('window.editor.view.nodeDOM('+str(target['position'])+').getBoundingClientRect().top')
    assert bar.get_y()+bar.get_height()+10<=top<=bar.get_y()+bar.get_height()+25,top
    assert js('window.editor.getState()')==before
    window.file_actions['document-outline'].activate(None);pump(lambda:panel.widget.get_visible() and len(panel.rows)==4)
    assert panel.list.get_selected_row().heading['position']==target['position']
    window.command('insertText',{'text':'Changed '});pump(lambda:panel.data['headings'][-1]['text'].startswith('Changed '))
    window.search.show();pump();assert not panel.widget.get_visible() and window.search.widget.get_visible()
    window.file_actions['document-outline'].activate(None);pump(lambda:panel.widget.get_visible())
    assert not window.search.widget.get_visible()
    js('window.editor.loadHTML("<p>No headings yet.</p>")');pump(lambda:len(panel.rows)==0)
    click(220,500);pump(lambda:not panel.widget.get_visible())
    assert not window.outline_button.get_active()
    menu=window.menu_button.get_menu_model();items=0
    for i in range(menu.get_n_items()):
        section=menu.get_item_link(i,Gio.MENU_LINK_SECTION)
        if section:
            for j in range(section.get_n_items()):
                label=section.get_item_attribute_value(j,Gio.MENU_ATTRIBUTE_LABEL,None)
                if label and label.get_string()=='Document outline':
                    assert section.get_item_link(j,Gio.MENU_LINK_SUBMENU) is None;items+=1
    assert items==1
    x11.XCloseDisplay(display)
    print('PASS: far-right outline icon, one menu item, centred regular-font hierarchical dropdown in all themes, real click navigation below toolbar, live updates, empty state and search/outside-click handling',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
