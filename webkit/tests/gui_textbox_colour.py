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
    from gi.repository import Gdk
    folder=ROOT/'.runtime/textbox-colour';folder.mkdir(parents=True,exist_ok=True)
    js('window.editor.loadHTML("<p>Rounded text box</p><p>Text wraps beside the coloured box.</p>")');js('window.editor.select(1)')
    window.action_buttons['textbox'].emit('clicked');pump(lambda:window.textbox_window is not None)
    def descendants(widget):
        yield widget;child=widget.get_first_child()
        while child:yield from descendants(child);child=child.get_next_sibling()
    def open_chooser():
        button=next(w for w in descendants(window.textbox_colour) if isinstance(w,Gtk.Button))
        button.emit('clicked')
        found=[]
        def detect():
            found[:]=[w for w in Gtk.Window.get_toplevels() if isinstance(w,Gtk.ColorChooserDialog)]
            return bool(found)
        pump(detect);return found[0]
    chooser=open_chooser()
    selected=Gdk.RGBA();selected.parse('#ffd966');chooser.set_rgba(selected)
    pump(minimum=.2);subprocess.run(['import','-window','root',str(folder/'standard-colour-chooser.png')],check=True)
    chooser.response(Gtk.ResponseType.OK);pump()
    window.textbox_controls['width'].set_value(250)
    window.textbox_window.response('insert');pump(lambda:bool(window.state.get('textbox')))
    properties=js('(()=>{const e=document.querySelector(".text-box"),s=getComputedStyle(e);return {radius:s.borderRadius,background:s.backgroundColor}})()')
    assert properties=={'radius':'12px','background':'rgb(255, 217, 102)'},properties
    assert js('window.editor.getState()')['json']['content'][0]['content'][0]['content'][0]['text']=='Rounded text box'
    pump(minimum=.2);subprocess.run(['import','-window','root',str(folder/'rounded-box.png')],check=True)
    # Editing a box reuses current settings; cancelling the chooser keeps its colour.
    window.action_buttons['textbox'].emit('clicked');pump(lambda:window.textbox_window is not None)
    assert window.textbox_window.get_heading()=='Text box properties'
    assert window.textbox_controls['width'].get_value_as_int()==250
    chooser=open_chooser();chooser.response(Gtk.ResponseType.CANCEL);pump()
    window.textbox_window.response('insert');pump()
    assert js('getComputedStyle(document.querySelector(".text-box")).backgroundColor')=='rgb(255, 217, 102)'
    before=js('window.editor.getState()')['json'];exported=js('window.editor.exportHTML()')['html']
    import json
    js('window.editor.loadHTML('+json.dumps(exported)+')')
    assert js('window.editor.getState()')['json']==before
    js('window.editor.select(2)');pump()
    window.action_buttons['textbox'].emit('clicked');pump(lambda:window.textbox_window is not None)
    window.textbox_reset.emit('clicked');window.textbox_window.response('insert');pump()
    assert js('window.editor.getTextbox()')['background'] is None
    window.command('undo');pump()
    assert js('getComputedStyle(document.querySelector(".text-box")).backgroundColor')=='rgb(255, 217, 102)'
    print('PASS: actual GTK standard colour chooser, rounded corners, chosen colour, editing existing box, cancel, default reset, undo and HTML round trip',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
