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
    from gi.repository import Gio
    import struct,zlib
    folder=ROOT/'.runtime/image-picker';folder.mkdir(parents=True,exist_ok=True)
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    width,height=64,48
    rows=b''.join(b'\0'+b''.join(bytes((x*4,y*5,160)) for x in range(width)) for y in range(height))
    path=folder/'picture.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
    window.action_buttons['photo'].emit('clicked');pump(lambda:window.image_chooser is not None)
    chooser=window.image_chooser;assert isinstance(chooser,Gtk.FileChooserNative)
    window.image_dialog();assert window.image_chooser is chooser
    chooser.emit('response',Gtk.ResponseType.CANCEL);pump()
    assert window.image_chooser is None and not js('window.editor.getSummary()')['dirty']
    window.image_dialog();chooser=window.image_chooser
    chooser.set_file(Gio.File.new_for_path(str(path)));pump(minimum=.3)
    assert chooser.get_file().get_path()==str(path)
    chooser.emit('response',Gtk.ResponseType.ACCEPT)
    pump(lambda:js('document.querySelectorAll(".ProseMirror img:not(.ProseMirror-separator)").length')==1)
    pump(lambda:js('document.querySelector(".ProseMirror img:not(.ProseMirror-separator)").naturalWidth')==width)
    image=js('(()=>{const e=document.querySelector(".ProseMirror img:not(.ProseMirror-separator)");return {width:e.naturalWidth,height:e.naturalHeight,src:e.getAttribute("src")}})()')
    assert image['width']==width and image['height']==height and image['src'].startswith('data:image/png;base64,')
    assert window.image_chooser is None
    exported=js('window.editor.exportHTML()')['html'];assert 'data:image/png;base64,' in exported
    print('PASS: native image picker, cancellation, single-dialog lifetime, real selected PNG insertion/decoding and embedded HTML export',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
