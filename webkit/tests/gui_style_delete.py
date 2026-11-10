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
    from toolbar import style_dialog
    js('window.editor.loadHTML("<p>Styled paragraph</p><p>Other paragraph</p>")')
    window.command('defineStyle',{'name':'My body','create':True});pump(lambda:'My body' in window.style_delete_buttons)
    original=js('window.editor.getState()')['json']
    assert all(name not in window.style_delete_buttons for name in ('Normal','Title','H1','H2','H3'))
    window.styles.popup();pump()
    window.style_delete_buttons['My body'].emit('clicked')
    pump(lambda:'My body' not in window.style_buttons)
    assert window.state['format']['style']=='Normal'
    assert js('window.editor.getText()')=='Styled paragraph\nOther paragraph'
    window.command('undo');pump(lambda:'My body' in window.style_buttons)
    assert window.state['format']['style']=='My body'
    assert js('window.editor.getState()')['json']==original
    style_dialog(window,False);pump()
    assert window.style_delete_button.get_label()=='Delete style'
    window.style_delete_button.emit('clicked');pump(lambda:'My body' not in window.state['styles'])
    assert 'My body' not in window.style_delete_buttons
    window.command('undo');pump(lambda:'My body' in window.style_delete_buttons)
    assert js('window.editor.getState()')['json']==original
    folder=ROOT/'.runtime/style-delete';folder.mkdir(parents=True,exist_ok=True)
    window.styles.popup();pump(minimum=.2)
    subprocess.run(['import','-window','root',str(folder/'dropdown.png')],check=True)
    window.styles.popdown()
    print('PASS: custom-style dropdown and dialog deletion, protected built-ins, fallback formatting and one-step undo restore the style and menu',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
