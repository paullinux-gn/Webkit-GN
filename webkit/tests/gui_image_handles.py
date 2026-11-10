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
    import ctypes as C
    x11=C.CDLL('libX11.so.6');xtest=C.CDLL('libXtst.so.6')
    x11.XOpenDisplay.argtypes=[C.c_char_p];x11.XOpenDisplay.restype=C.c_void_p
    x11.XFlush.argtypes=[C.c_void_p];x11.XCloseDisplay.argtypes=[C.c_void_p]
    xtest.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
    xtest.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    display=x11.XOpenDisplay(None);assert display
    def move(x,y):
        xtest.XTestFakeMotionEvent(display,-1,round(x),round(y),0);x11.XFlush(display);pump(minimum=.04)
    def press(down):
        xtest.XTestFakeButtonEvent(display,1,down,0);x11.XFlush(display);pump(minimum=.05)
    def rect(selector):return js('(()=>{const r=document.querySelector('+__import__('json').dumps(selector)+').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,width:r.width,height:r.height}})()')
    image_selector='.ProseMirror img:not(.ProseMirror-separator)'
    position=rect(image_selector);move(position['x'],position['y']);press(True);press(False)
    pump(lambda:js('!document.querySelector(".image-resize-controls").hidden'))
    original=js('window.editor.getState()')
    handle=rect('.image-resize-handle.corner');move(handle['x'],handle['y']);press(True)
    move(handle['x']+80,handle['y']+40)
    assert js('window.editor.view.dom.querySelector("img:not(.ProseMirror-separator)").clientWidth')>400
    assert js('window.editor.getState()')==original,'Dragging changed history before release'
    press(False);pump(lambda:js('window.editor.getImage(1).width') is not None)
    width=js('window.editor.getImage(1).width');assert abs(width-464)<=2,width
    dimensions=rect(image_selector);assert abs(dimensions['width']/dimensions['height']-2)<.02,dimensions
    assert 'image-resize' not in js('window.editor.exportHTML()')['html']
    folder=ROOT/'.runtime/image-handles';folder.mkdir(parents=True,exist_ok=True)
    subprocess.run(['import','-window','root',str(folder/'selected.png')],check=True)
    window.command('undo');pump(lambda:js('window.editor.getImage(1).width===null'))
    assert js('window.editor.getState()')['json']==original['json']
    # Escape restores the image without creating an undo entry.
    before=js('window.editor.getState()');handle=rect('.image-resize-handle.right')
    move(handle['x'],handle['y']);press(True);move(handle['x']-50,handle['y'])
    js('document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true,cancelable:true}))')
    press(False);assert js('window.editor.getState()')==before
    assert js('window.editor.view.dom.querySelector("img:not(.ProseMirror-separator)").clientWidth')==400
    # Confirm the size dialog still works with the image node view.
    js('window.editor.view.dom.querySelector("img:not(.ProseMirror-separator)").dispatchEvent(new MouseEvent("dblclick",{bubbles:true,cancelable:true}))')
    pump(lambda:getattr(window,'image_size_window',None) is not None)
    window.image_size_window.response('cancel');pump()
    x11.XCloseDisplay(display)
    print('PASS: real image selection and handle drag at 125%, live proportional preview, one-step undo, Escape cancellation, clean HTML and double-click dialog',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
