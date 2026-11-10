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
        assert time.monotonic()-start<20,(errors,getattr(getattr(window,'print_preview',None),'label',window.status).get_text())
        for _ in range(100):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.003)
    assert not errors,errors

def js(text):
    result=[];window.js(text,result.append);pump(lambda:bool(result));return result[0]
try:
    pump(lambda:window.state.get('ready'));print('READY',flush=True)
    import struct,zlib,json
    from document_io import image_uri
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    image_width,image_height=400,200
    rows=b''.join(b'\0'+bytes((50,140,190))*image_width for _ in range(image_height))
    path=ROOT/'.runtime/resize-test.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',image_width,image_height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
    js('window.editor.loadHTML('+json.dumps('<p><img src="'+image_uri(path)+'" alt="Test picture"></p>')+')')
    pump(minimum=.5)
    pump(lambda:js('window.editor.view.dom.querySelector("img:not(.ProseMirror-separator)").naturalWidth')==400);print('IMAGE READY',flush=True)
    js('window.editor.view.dom.querySelector("img:not(.ProseMirror-separator)").dispatchEvent(new MouseEvent("dblclick",{bubbles:true,cancelable:true}))')
    pump(lambda:getattr(window,'image_size_window',None) is not None);print('DIALOG OPEN',flush=True)
    controls=window.image_size_controls;controls['width'].set_value(200)
    assert controls['height'].get_value_as_int()==100
    window.image_size_window.response('apply');pump(lambda:js('window.editor.getImage(1).width')==200)
    assert js('window.editor.view.dom.querySelector("img:not(.ProseMirror-separator)").clientWidth')==200;print('WIDTH APPLIED',flush=True)
    window.action_buttons['photo'].emit('clicked');pump(lambda:window.image_size_window is not None)
    controls=window.image_size_controls;controls['height'].set_value(60)
    assert controls['width'].get_value_as_int()==120
    window.image_size_window.response('apply');pump(lambda:js('window.editor.getImage(1).width')==120)
    saved=js('window.editor.exportHTML()')['html']
    js('window.editor.loadHTML('+json.dumps(saved)+')')
    pump(minimum=.5)
    pump(lambda:js('window.editor.view.dom.querySelector("img:not(.ProseMirror-separator)").naturalWidth')==400);print('IMAGE READY',flush=True)
    assert js('window.editor.getImage(1).width')==120
    js('window.editor.view.dom.querySelector("img:not(.ProseMirror-separator)").dispatchEvent(new MouseEvent("dblclick",{bubbles:true,cancelable:true}))')
    pump(lambda:window.image_size_window is not None)
    window.image_size_window.response('original');pump(lambda:js('window.editor.getImage(1).width===null'))
    assert js('window.editor.view.dom.querySelector("img:not(.ProseMirror-separator)").clientWidth')==400
    window.command('undo');pump(lambda:js('window.editor.getImage(1).width')==120)
    print('PASS: double-click and toolbar open Picture size, width/height stay proportional, displayed image resizes, HTML retains size, Original size and undo work',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
