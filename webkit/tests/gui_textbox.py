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
    folder=ROOT/'.runtime/textbox';folder.mkdir(parents=True,exist_ok=True)
    js('window.editor.loadHTML("<p>Text inside the box.</p><p>Following text wraps beside the text box. Following text wraps beside the text box. Following text wraps beside the text box.</p>")')
    js('window.editor.select(1)')
    window.action_buttons['textbox'].emit('clicked');pump(lambda:window.textbox_window is not None)
    controls=window.textbox_controls
    assert controls['width'].get_value_as_int()==150 and controls['height'].get_value_as_int()==100
    assert controls['borderWidth'].get_value_as_int()==1 and controls['floating'].get_active()
    pump(minimum=.2);subprocess.run(['import','-window','root',str(folder/'insert-textbox.png')],check=True)
    controls['width'].set_value(240);controls['height'].set_value(120);controls['borderWidth'].set_value(3)
    window.textbox_window.response('insert');pump()
    data=js('window.editor.getState()')['json'];box=data['content'][0]
    assert box['type']=='textbox' and box['attrs']=={'width':240,'height':120,'borderWidth':3,'floating':True,'background':None}
    layout=js('(()=>{const b=document.querySelector("section[data-textbox]"),p=Array.from(document.querySelectorAll(".ProseMirror > p")).find(p=>p.textContent.includes("Following text")),r=document.createRange();r.setStart(p.firstChild,0);r.setEnd(p.firstChild,9);return {right:b.getBoundingClientRect().right,width:b.getBoundingClientRect().width,height:b.getBoundingClientRect().height,text:r.getBoundingClientRect().left,border:getComputedStyle(b).borderTopWidth}})()')
    assert layout['text']>layout['right'] and layout['border']=='3px',layout
    assert abs(layout['width']-300)<1 and layout['height']>=150,layout
    js('window.editor.exec("insertText",{text:"Extra text inside the box. " .repeat(30)})');pump()
    assert js('document.querySelector("section[data-textbox]").getBoundingClientRect().height')>layout['height']
    assert js('(()=>{const e=document.querySelector("section[data-textbox]");return e.scrollHeight<=e.clientHeight+1})()')
    before=js('window.editor.getState()')['json'];exported=js('window.editor.exportHTML()')['html']
    import json
    js('window.editor.loadHTML('+json.dumps(exported)+')')
    assert js('window.editor.getState()')['json']==before
    window.action_buttons['textbox'].emit('clicked');pump();window.textbox_window.response('cancel');pump()
    assert js('window.editor.getState()')['json']==before
    print('PASS: native text-box dialog, exact zoomed dimensions, border width, real text wrapping, expansion without clipping, save/reload and cancel',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
