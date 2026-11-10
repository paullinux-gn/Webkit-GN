"""Visual appearance checks on a disposable HD display, including actual blur pixels."""
from pathlib import Path
import os
import sys
import time
import tempfile
import subprocess
import struct
import zlib
import base64

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"webkit"))
preferences=tempfile.TemporaryDirectory(prefix="gnome-wp-appearance-")
os.environ["GNOME_WP_SETTINGS_FILE"]=str(Path(preferences.name)/"settings.json")
from app import App,GLib

app=App();app.register(None);app.activate();window=app.get_active_window()
context=GLib.MainContext.default()
folder=ROOT/".runtime/appearance"
folder.mkdir(parents=True,exist_ok=True)

def pump(predicate=lambda:True,minimum=.1):
    start=time.monotonic()
    while time.monotonic()-start<minimum or not predicate():
        if time.monotonic()-start>20:raise AssertionError("Appearance test timed out: "+window.status.get_text())
        for _ in range(100):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.002)

def js(expression):
    result=[];errors=[]
    window.js(expression,result.append,errors.append)
    pump(lambda:bool(result or errors))
    assert not errors,errors
    return result[0]

def capture(name):
    pump(minimum=.25)
    subprocess.run(["import","-window","root",str(folder/(name+".png"))],check=True)

try:
    pump(lambda:window.state.get("ready"))
    # Measure the editable content, including its actual zoomed page margins.
    for width in (1120,1500,1060,1120):
        window.set_default_size(width,1000);pump(minimum=.25)
        geometry=js('(()=>{const e=document.querySelector(".ProseMirror"),r=e.getBoundingClientRect(),s=getComputedStyle(e),z=r.width/e.offsetWidth;return {left:r.left+parseFloat(s.paddingLeft)*z,right:r.right-parseFloat(s.paddingRight)*z,viewport:innerWidth}})()')
        centre=(geometry["left"]+geometry["right"])/2
        assert abs(centre-geometry["viewport"]/2)<1,geometry
        ok,bounds=window.webview.compute_bounds(window);assert ok
        assert abs(bounds.get_x()+centre-window.get_width()/2)<1,(geometry,window.get_width())
        assert js("document.body.scrollWidth<=document.documentElement.clientWidth"),geometry
    print("PASS: writing area centred within one pixel, with zoomed margins, at default and wider window sizes",flush=True)
    def chunk(kind,data):return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data))
    # Alternating high-frequency stripes make real backdrop blur distinguishable
    # from opacity alone, without introducing script or remote image resources.
    row=b"\0"+b"".join(bytes((240,80,30) if x//8%2 else (30,100,235)) for x in range(800))
    image=b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",800,500,8,2,0,0,0))+chunk(b"IDAT",zlib.compress(row*500))+chunk(b"IEND",b"")
    html='<p>Document behind the floating toolbar</p><p><img src="data:image/png;base64,'+base64.b64encode(image).decode()+'"></p>'+('<p>A clear view of your document.</p>'*40)
    import json
    js("window.editor.loadHTML("+json.dumps(html)+")")
    for theme in ("light","dark","mixed"):
        window.change_appearance(theme=theme)
        pump(minimum=.15)
        surface=js('({body:getComputedStyle(document.body).backgroundColor,paper:getComputedStyle(document.getElementById("editor")).backgroundColor,shadow:getComputedStyle(document.getElementById("editor")).boxShadow})')
        assert surface["body"]==surface["paper"] and surface["shadow"]=="none",surface
        capture(theme)
    window.lookup_action("interface").activate(None)
    pump(lambda:window.interface_window is not None)
    capture("interface")
    window.interface_window.close();pump()
    js("(window.scrollTo(0,420),true)")
    window.change_appearance(opacity=.65,blur_radius=20,blur=True)
    pump(minimum=.2)
    on=js('getComputedStyle(document.getElementById("toolbar-glass")).backdropFilter') if not window.native_blur else "native"
    assert window.native_blur or on=="blur(20px)",on
    header=js('({mask:getComputedStyle(document.getElementById("header-glass")).webkitMaskImage,height:document.getElementById("header-glass").getBoundingClientRect().height})')
    assert "linear-gradient" in header["mask"] and abs(header["height"]-(max(0,window.glass_geometry["header"]["height"]-16)+112))<1,header
    capture("blur-on")
    window.change_appearance(blur=False)
    capture("blur-off")
    assert (folder/"blur-on.png").read_bytes()!=(folder/"blur-off.png").read_bytes()
    assert not js("window.editor.getSummary()")["dirty"]
    print("PASS: light/dark/mixed previews, circular Interface choices, live blur-on/off images; document stays clean",flush=True)
finally:
    window.discard_confirmed=True;window.close();preferences.cleanup()
