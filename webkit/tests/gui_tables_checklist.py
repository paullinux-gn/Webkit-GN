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
    folder=ROOT/'.runtime/tables-checklist';folder.mkdir(parents=True,exist_ok=True)
    js('window.editor.loadHTML("<p></p><p>Following text wraps beside a floating table. Following text wraps beside a floating table. Following text wraps beside a floating table.</p>")')
    js('window.editor.select(1)')
    window.action_buttons['table'].emit('clicked');pump(lambda:window.table_window is not None)
    controls=window.table_controls
    assert controls['rows'].get_value_as_int()==3 and controls['header'].get_active()
    subprocess.run(['import','-window','root',str(folder/'insert-table.png')],check=True)
    controls['rows'].set_value(4);controls['cols'].set_value(2);controls['borderWidth'].set_value(3)
    controls['width'].set_selected(1);controls['floating'].set_active(True)
    window.table_window.response('insert');pump()
    data=js('window.editor.getState()')['json'];table=data['content'][0]
    assert table['type']=='table' and len(table['content'])==4
    assert table['content'][0]['content'][0]['type']=='table_header'
    assert table['attrs']=={'borderWidth':3,'width':50,'floating':True}
    layout=js('(()=>{const t=document.querySelector(".tableWrapper"),p=Array.from(document.querySelectorAll(".ProseMirror > p")).find(p=>p.textContent.includes("Following text")),r=document.createRange();r.setStart(p.firstChild,0);r.setEnd(p.firstChild,9);return {table:t.getBoundingClientRect().right,text:r.getBoundingClientRect().left,border:getComputedStyle(t.querySelector("td")).borderTopWidth}})()')
    assert layout['text']>layout['table'] and layout['border']=='3px',layout
    pump(minimum=.2);subprocess.run(['import','-window','root',str(folder/'floating-table.png')],check=True)
    before=js('window.editor.getState()')['json'];exported=js('window.editor.exportHTML()')['html']
    import json
    js('window.editor.loadHTML('+json.dumps(exported)+')')
    assert js('window.editor.getState()')['json']==before
    window.action_buttons['table'].emit('clicked');pump();window.table_window.response('cancel');pump()
    assert js('window.editor.getState()')['json']==before
    print('PASS: native table dialog, header row, border width, 50% width, actual text wrapping, save/reload and cancel',flush=True)
    js('window.editor.loadHTML("<p>Checklist task</p>")');js('window.editor.select(1)')
    window.action_buttons['checklist'].emit('clicked');pump(lambda:window.state['format']['checklist'])
    assert window.toggle_buttons['checklist'].get_active()
    js('(()=>{document.querySelector("input[type=checkbox]").click();return true})()');pump()
    assert js('window.editor.getState()')['json']['content'][0]['content'][0]['attrs']['checked']
    window.command('undo');pump()
    assert not js('window.editor.getState()')['json']['content'][0]['content'][0]['attrs']['checked']
    window.command('redo');pump()
    assert js('window.editor.getState()')['json']['content'][0]['content'][0]['attrs']['checked']
    subprocess.run(['import','-window','root',str(folder/'checklist.png')],check=True)
    print('PASS: checklist toolbar toggle, live checkbox, separate undo/redo and active formatting state',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
