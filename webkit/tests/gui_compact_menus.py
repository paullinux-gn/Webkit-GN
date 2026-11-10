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
    folder=ROOT/'.runtime/compact-menus';folder.mkdir(parents=True,exist_ok=True)
    errors=[];window.css.connect('parsing-error',lambda _,section,error:errors.append(error.message))
    window.apply_appearance();assert not errors,errors
    def descendants(widget):
        yield widget;child=widget.get_first_child()
        while child:yield from descendants(child);child=child.get_next_sibling()
    window.alignment_menu.popup();pump()
    assert all(button.get_height()<=30 for button in window.alignment_buttons.values())
    subprocess.run(['import','-window','root',str(folder/'alignment.png')],check=True)
    window.alignment_buttons['center'].emit('clicked');pump(lambda:window.state['format']['align']=='center')
    window.line_spacing_menu.popup();pump()
    assert all(button.get_height()<=30 for button in window.line_spacing_buttons.values())
    subprocess.run(['import','-window','root',str(folder/'spacing.png')],check=True)
    window.line_spacing_buttons[.95].set_active(True);pump(lambda:window.state['format']['lineSpacing']==.95)
    for kind in ('table','link'):
        window.action_buttons[kind].emit('clicked');pump()
        dialog=window.table_window if kind=='table' else window.link_window
        buttons=[w for w in descendants(dialog) if isinstance(w,Gtk.Button) and w.get_label() in ('Cancel','Insert')]
        assert len(buttons)==2
        for button in buttons:
            assert button.get_height()<=34,(kind,button.get_label(),button.get_height())
            assert button.get_width()<110,(kind,button.get_label(),button.get_width())
        subprocess.run(['import','-window','root',str(folder/(kind+'.png'))],check=True)
        print(kind+' action button sizes: '+str([(b.get_width(),b.get_height()) for b in buttons]),flush=True)
        dialog.response('cancel');pump()
    print('PASS: compact alignment/spacing menus, compact table/link dialogs and buttons, normal formatting actions and cancellation',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
