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
    # Exercise the WebKit backdrop fallback used by the affected Flatpak runtime.
    window.native_blur=False
    js('window.editor.loadHTML("<h1>Blur alignment</h1><p>Document content behind the toolbar.</p>")')
    for zoom in (1,1.1,1.25,1.5):
        window.webview.set_zoom_level(zoom);pump(minimum=.25)
        window.change_appearance(blur=True,opacity=.65,blur_radius=18);pump(minimum=.25)
        for name,panel in (('toolbar',None),('search',window.search),('outline',window.outline)):
            if panel:panel.show();pump(minimum=.2)
            window.update_glass_geometry();window.apply_web_appearance();pump(minimum=.15)
            expected=window.glass_geometry[name]
            measured=js('(()=>{const e=document.getElementById("'+name+'-glass"),r=e.getBoundingClientRect();return {left:r.left,top:r.top,width:r.width,height:r.height,display:getComputedStyle(e).display}})()')
            assert measured['display']=='block',measured
            for key in ('left','top','width','height'):
                actual=measured[key]*zoom
                assert abs(actual-expected[key])<1.5,(zoom,name,key,actual,expected[key],measured)
            if panel:panel.hide(False);pump()
        if zoom==1.1:
            folder=ROOT/'.runtime/blur-scaling';folder.mkdir(parents=True,exist_ok=True)
            subprocess.run(['import','-window','root',str(folder/'aligned.png')],check=True)
        print('PASS: toolbar/search/outline backdrops align at WebKit zoom',zoom,flush=True)
    window.change_appearance(blur=False);pump()
    assert js('getComputedStyle(document.getElementById("toolbar-glass")).display')=='none'
    assert not js('window.editor.getSummary()')['dirty']
    print('PASS: blur off restores solid surfaces and document stays clean',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
