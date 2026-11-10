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
    from app import Adw
    folder=ROOT/'.runtime/ui-surfaces';folder.mkdir(parents=True,exist_ok=True)
    css_errors=[];window.css.connect('parsing-error',lambda _,section,error:css_errors.append(error.message))
    def descendants(widget):
        yield widget;child=widget.get_first_child()
        while child:yield from descendants(child);child=child.get_next_sibling()
    def ink(widget):
        c=widget.get_color();return tuple(round(v*255) for v in (c.red,c.green,c.blue))
    for theme,expected in (('light',(32,33,36)),('dark',(242,243,245)),('mixed',(242,243,245))):
        window.change_appearance(theme=theme);pump()
        assert not css_errors,css_errors
        assert Adw.StyleManager.get_default().get_dark()==(theme!='light')
        assert js('getComputedStyle(document.body).backgroundColor')==('rgb(37, 39, 45)' if theme=='dark' else 'rgb(255, 255, 255)')
        window.menu_button.popup();pump()
        popover=window.menu_button.get_popover()
        content=next(w for w in descendants(popover) if w.get_css_name()=='contents')
        assert ink(content)==expected,(theme,ink(content))
        subprocess.run(['import','-window','root',str(folder/(theme+'-hamburger.png'))],check=True)
        window.menu_button.popdown();window.action_buttons['table'].emit('clicked');pump(lambda:window.table_window is not None)
        assert ink(window.table_window)==expected,(theme,ink(window.table_window))
        subprocess.run(['import','-window','root',str(folder/(theme+'-table.png'))],check=True)
        window.table_window.response('cancel');pump()
        window.show_interface();pump()
        assert ink(window.interface_window)==expected,(theme,ink(window.interface_window))
        subprocess.run(['import','-window','root',str(folder/(theme+'-interface.png'))],check=True)
        window.interface_window.close();pump()
        window.choose_file(False);pump(lambda:window.file_chooser.get_visible())
        assert isinstance(window.file_chooser,Gtk.FileChooserDialog)
        assert ink(window.file_chooser)==expected,(theme,ink(window.file_chooser))
        window.file_chooser.response(Gtk.ResponseType.CANCEL);pump()
    print('PASS: all themes, matching hamburger/dropdown/dialog/settings/file-chooser colours, preserved document colours and no CSS parse errors',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
