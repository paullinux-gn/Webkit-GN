"""Native WebKitGTK/ProseMirror workflow test on a disposable X11 display."""
import base64
import ctypes as C
from pathlib import Path
import subprocess
import sys
import time
import struct
import zlib
import os
import tempfile
import json

ROOT=Path(__file__).resolve().parents[2]
preferences=tempfile.TemporaryDirectory(prefix="gnome-wp-interface-test-")
os.environ["GNOME_WP_SETTINGS_FILE"]=str(Path(preferences.name)/"interface.json")
sys.path.insert(0,str(ROOT/"webkit"))
from app import App,GLib,Gio,Gtk
import gi
gi.require_version("GdkX11","4.0")
from gi.repository import GdkX11

errors=[]
original_hook=sys.excepthook
def record(kind,error,tb):
    errors.append(str(error));original_hook(kind,error,tb)
sys.excepthook=record
app=App();app.register(None);app.activate();window=app.get_active_window()
context=GLib.MainContext.default()
beats=[]
timer=GLib.timeout_add(20,lambda:(beats.append(time.monotonic()),True)[1])


def pump(predicate=lambda:True,timeout=30,minimum=0.05):
    start=time.monotonic()
    while time.monotonic()-start<minimum or not predicate():
        if time.monotonic()-start>timeout:
            raise AssertionError("Timed out: "+window.status.get_text())
        for _ in range(100):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.002)
    assert not errors,errors


def evaluate(expression):
    values=[];failures=[]
    window.js(expression,values.append,failures.append)
    pump(lambda:bool(values or failures))
    assert not failures,failures
    return values[0]


x11=C.CDLL("libX11.so.6");xtest=C.CDLL("libXtst.so.6")
x11.XOpenDisplay.argtypes=[C.c_char_p];x11.XOpenDisplay.restype=C.c_void_p
x11.XStringToKeysym.argtypes=[C.c_char_p];x11.XStringToKeysym.restype=C.c_ulong
x11.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x11.XKeysymToKeycode.restype=C.c_uint
x11.XSetInputFocus.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_ulong]
x11.XFlush.argtypes=[C.c_void_p];x11.XCloseDisplay.argtypes=[C.c_void_p]
xtest.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
xtest.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
xtest.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
display=x11.XOpenDisplay(None)
assert display,"Use a disposable X11 display"


def key(name,modifiers=()):
    def send(symbol,down):
        code=x11.XKeysymToKeycode(display,x11.XStringToKeysym(symbol.encode()))
        assert code,symbol
        xtest.XTestFakeKeyEvent(display,code,down,0)
    for modifier in modifiers:send(modifier,True)
    send(name,True);send(name,False)
    for modifier in reversed(modifiers):send(modifier,False)
    x11.XFlush(display)


try:
    pump(lambda:window.state.get("ready"))
    pump(minimum=.2)
    bounds=evaluate('({width:document.getElementById("editor").getBoundingClientRect().width,height:document.getElementById("editor").getBoundingClientRect().height})')
    assert abs(bounds["width"]-992.5)<2,bounds
    assert bounds["height"]>=1403,bounds
    assert window.get_width()<=1122,window.get_width()
    assert window.appearance["theme"]=="mixed"
    window.lookup_action("interface").activate(None)
    pump(lambda:window.interface_window is not None)
    for theme, paper in (("dark","rgb(37, 39, 45)"),("light","rgb(255, 255, 255)"),("mixed","rgb(255, 255, 255)")):
        window.theme_buttons[theme].set_active(True)
        pump(minimum=.1)
        assert evaluate('document.documentElement.dataset.theme')==theme
        assert evaluate('getComputedStyle(document.getElementById("editor")).backgroundColor')==paper
        assert window.tools.has_css_class("dark-toolbar")== (theme!="light")
    window.opacity_slider.set_value(65);window.blur_slider.set_value(22)
    pump(minimum=.35)
    saved_preferences=json.loads(Path(os.environ["GNOME_WP_SETTINGS_FILE"]).read_text())
    assert saved_preferences["opacity"]==.65 and saved_preferences["blur_radius"]==22
    assert not evaluate("window.editor.getSummary()")["dirty"]
    if not window.native_blur:
        assert evaluate('getComputedStyle(document.getElementById("toolbar-glass")).backdropFilter')=="blur(22px)"
    window.blur_switch.set_active(False);pump(minimum=.1)
    assert not window.blur_slider.get_sensitive()
    if not window.native_blur:
        assert evaluate('getComputedStyle(document.getElementById("toolbar-glass")).display')=="none"
    window.blur_switch.set_active(True);window.opacity_slider.set_value(88);window.blur_slider.set_value(14)
    window.interface_window.close();pump(minimum=.15)
    print("PASS: 125% A4 view and fitted window, hamburger Interface, three themes, persistent opacity/blur sliders; document remains clean",flush=True)
    folder=ROOT/".runtime/webkit-gui"
    folder.mkdir(parents=True,exist_ok=True)
    # A genuine PNG fixture. The Python I/O layer must embed it before WebKit import.
    image=folder/"image.png"
    def chunk(kind,data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data))
    row=b"\0"+b"".join(bytes((x%256,120,255-x%256)) for x in range(1600))
    image.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",1600,1000,8,2,0,0,0))+
                      chunk(b"IDAT",zlib.compress(row*1000))+chunk(b"IEND",b""))
    paragraphs="".join(f'<p>Paragraph {i}: '+"A long native editor document with Unicode café and Ελληνικά. "*8+'</p>' for i in range(1200))
    source=folder/"input.html"
    source.write_text('<!doctype html><html><body><h1>Long document</h1><p><img src="image.png" alt="sample"></p>'+paragraphs+'</body></html>',encoding="utf-8")

    window.menu_button.grab_focus()
    x11.XSetInputFocus(display,window.get_surface().get_xid(),1,0);x11.XFlush(display)
    key("o",("Control_L",))
    pump(lambda:window.file_chooser is not None)
    chooser=window.file_chooser
    chooser.set_file(Gio.File.new_for_path(str(source)))
    pump(minimum=.3)
    assert chooser.get_file().get_path()==str(source)
    chooser.emit("response",Gtk.ResponseType.ACCEPT)
    pump(lambda:window.path==source and not window.file_busy,timeout=60)
    x11.XSetInputFocus(display,window.get_surface().get_xid(),1,0);x11.XFlush(display)
    pump()
    assert window.webview.has_focus(),"Native Open did not return keyboard focus to the editor"
    start=time.monotonic();key("x");pump(minimum=.2)
    text=evaluate("window.editor.getText()")
    assert text.startswith("xLong document"),text[:80]
    assert evaluate('document.querySelectorAll(".ProseMirror img:not(.ProseMirror-separator)").length')==1
    assert evaluate('document.querySelector(".ProseMirror img:not(.ProseMirror-separator)").naturalWidth')==1600
    print(f"PASS: native Open → 1200-paragraph HTML + image → real typing ({1000*(time.monotonic()-start):.0f} ms including test wait)",flush=True)

    evaluate('window.editor.exec("style",{name:"Normal"})')
    evaluate("window.editor.select(1,6)")
    bold=window.toggle_buttons["bold"]
    ok,bounds=bold.compute_bounds(window);assert ok
    xtest.XTestFakeMotionEvent(display,-1,round(bounds.get_x()+bounds.get_width()/2),round(bounds.get_y()+bounds.get_height()/2),0)
    xtest.XTestFakeButtonEvent(display,1,True,0);xtest.XTestFakeButtonEvent(display,1,False,0);x11.XFlush(display)
    pump(lambda:window.state["format"]["strong"])
    assert "<strong>xLong</strong>" in evaluate("window.editor.exportHTML()")["html"]
    assert window.webview.has_focus(),"Native toolbar lost editor focus"
    key("z",("Control_L",));pump(minimum=.1)
    assert "<strong>xLong</strong>" not in evaluate("window.editor.exportHTML()")["html"]
    key("z",("Control_L","Shift_L"));pump(minimum=.1)
    assert "<strong>xLong</strong>" in evaluate("window.editor.exportHTML()")["html"]
    print("PASS: native toolbar keeps selection; browser keyboard undo/redo",flush=True)

    saved=folder/"saved.html"
    if saved.exists():saved.unlink()
    key("s",("Control_L","Shift_L"))
    pump(lambda:window.file_chooser is not None)
    chooser=window.file_chooser
    chooser.set_current_folder(Gio.File.new_for_path(str(folder)))
    chooser.set_current_name(saved.name)
    pump(minimum=.3)
    chooser.emit("response",Gtk.ResponseType.ACCEPT)
    pump(lambda:saved.exists() and not window.file_busy,timeout=60)
    assert "data:image/png;base64," in saved.read_text()
    assert not evaluate("window.editor.getSummary()")["dirty"]
    image.unlink()
    window.open_path(saved)
    pump(lambda:window.path==saved and not window.file_busy)
    assert evaluate('document.querySelectorAll(".ProseMirror img:not(.ProseMirror-separator)").length')==1
    assert evaluate('document.querySelector(".ProseMirror img:not(.ProseMirror-separator)").naturalWidth')==1600
    assert evaluate("window.editor.getText()").startswith("xLong document")
    print("PASS: native Save As → self-contained HTML → reopen after original image removal",flush=True)

    evaluate("(window.editor.select(window.editor.view.state.doc.content.size-1), window.scrollTo(0,document.body.scrollHeight), true)")
    key("q");pump(minimum=.15)
    assert evaluate("window.editor.getText()").endswith("q")
    max_gap=max((b-a for a,b in zip(beats,beats[1:])),default=0)
    assert max_gap<.5,f"GTK main loop stalled {max_gap:.2f}s"
    assert window.webview.get_height()<=window.get_height()
    print(f"PASS: end-of-document scrolling and typing; largest GTK heartbeat gap {1000*max_gap:.1f} ms",flush=True)
    # Capture the user's disposable display, never their real desktop.
    evaluate("(window.scrollTo(0,0),true)")
    pump(minimum=.3)
    subprocess.run(["import","-window","root",str(folder/"screenshot.png")],check=True,timeout=10)
finally:
    GLib.source_remove(timer)
    window.discard_confirmed=True;window.file_busy=False;window.close()
    x11.XCloseDisplay(display)
    preferences.cleanup()
