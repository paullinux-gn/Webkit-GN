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
    folder=ROOT/'.runtime/table-edit';folder.mkdir(parents=True,exist_ok=True)
    window.command('table',{'rows':2,'cols':2,'header':True});pump(lambda:bool(window.state.get('table')))
    js('window.editor.exec("insertText",{text:"Existing cell content"})');pump()
    original=js('window.editor.getState()')['json']
    # Hit the visible properties handle with a real X11 pointer click.
    import ctypes as C
    x11=C.CDLL('libX11.so.6');xtest=C.CDLL('libXtst.so.6')
    x11.XOpenDisplay.argtypes=[C.c_char_p];x11.XOpenDisplay.restype=C.c_void_p
    x11.XFlush.argtypes=[C.c_void_p];x11.XCloseDisplay.argtypes=[C.c_void_p]
    xtest.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
    xtest.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    display=x11.XOpenDisplay(None);assert display
    bounds=js('(()=>{const r=document.querySelector("[data-table-properties]").getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()')
    xtest.XTestFakeMotionEvent(display,-1,round(bounds['x']),round(bounds['y']),0);x11.XFlush(display);pump()
    xtest.XTestFakeButtonEvent(display,1,True,0);xtest.XTestFakeButtonEvent(display,1,False,0);x11.XFlush(display)
    pump(lambda:window.table_window is not None)
    assert window.table_window.get_heading()=='Table properties'
    controls=window.table_controls;assert controls['rows'].get_value_as_int()==2
    assert controls['header'].get_active()
    controls['rows'].set_value(1);pump()
    assert 'removes cells' in window.table_window.get_body()
    controls['rows'].set_value(3);controls['cols'].set_value(3);controls['width'].set_selected(1)
    controls['borderWidth'].set_value(3);controls['floating'].set_active(True);controls['header'].set_active(False)
    subprocess.run(['import','-window','root',str(folder/'properties.png')],check=True)
    window.table_window.response('insert');pump()
    table=js('window.editor.getState()')['json']['content'][0]
    assert len(table['content'])==3 and len(table['content'][0]['content'])==3
    assert table['content'][0]['content'][0]['content'][0]['content'][0]['text']=='Existing cell content'
    assert table['attrs']=={'borderWidth':3,'width':50,'floating':True}
    window.command('undo');pump();assert js('window.editor.getState()')['json']==original
    window.command('redo');pump()
    # Toolbar reopens properties for the existing table, rather than inserting another.
    window.action_buttons['table'].emit('clicked');pump(lambda:window.table_window is not None)
    assert window.table_controls['rows'].get_value_as_int()==3
    window.table_window.response('cancel');pump()
    import json
    exported=js('window.editor.exportHTML()')['html'];js('window.editor.loadHTML('+json.dumps(exported)+')')
    # Double-clicking the outer table edge also opens properties after reopening.
    js('(()=>{const t=document.querySelector("table"),r=t.getBoundingClientRect();t.dispatchEvent(new MouseEvent("dblclick",{bubbles:true,clientX:r.left+1,clientY:r.top+2}));return true})()')
    pump(lambda:window.table_window is not None)
    assert window.table_controls['borderWidth'].get_value_as_int()==3
    window.table_window.response('cancel');pump()
    assert not js('window.editor.getSummary()')['dirty']
    x11.XCloseDisplay(display)
    print('PASS: real properties-handle click, populated dialog, destructive resize warning, content preservation, atomic undo/redo, toolbar edit and edge editing after HTML reopen',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
