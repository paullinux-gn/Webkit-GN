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
    window.show_interface();pump(lambda:window.interface_window is not None)
    dialog=window.interface_window
    assert dialog.get_default_size()[0]==392,dialog.get_default_size()
    assert 380<=dialog.get_width()<=392,dialog.get_width()
    assert dialog.get_height()>=540,dialog.get_height()
    for theme,button in window.theme_buttons.items():
        parent=button.get_parent()
        assert parent.get_first_child() is button and button.get_next_sibling() is None
        assert button.get_tooltip_text()
        button.set_active(True);pump()
        assert 380<=dialog.get_width()<=392,(theme,dialog.get_width())
        for control in (*window.theme_buttons.values(),window.opacity_slider,window.blur_slider):
            ok,bounds=control.compute_bounds(dialog);assert ok
            assert bounds.get_x()>=0 and bounds.get_x()+bounds.get_width()<=dialog.get_width(),(theme,bounds.get_x(),bounds.get_width())
    window.opacity_slider.set_value(70);window.blur_slider.set_value(20);pump(minimum=.3)
    assert window.appearance['opacity']==.7 and window.appearance['blur_radius']==20
    folder=ROOT/'.runtime/interface-narrow';folder.mkdir(parents=True,exist_ok=True)
    subprocess.run(['import','-window','root',str(folder/'interface.png')],check=True)
    dialog.close();pump()
    assert not js('window.editor.getSummary()')['dirty']
    print('PASS: Interface width 392px (30% narrower), circle-only theme choices with tooltips, all controls fit in every theme and sliders work',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
